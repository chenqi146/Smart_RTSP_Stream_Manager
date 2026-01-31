import os
import sys
import paramiko
from stat import S_ISDIR

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Manual fallback if python-dotenv is not installed
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"').strip("'")

# Configuration from Environment Variables
HOST = os.getenv('DEPLOY_HOST')
PORT = int(os.getenv('DEPLOY_PORT', 22))
USERNAME = os.getenv('DEPLOY_USER')
PASSWORD = os.getenv('DEPLOY_PASSWORD')
REMOTE_PATH = '/data/Smart_RTSP_Stream_Manager'

# Files/Directories to ignore during deployment
IGNORE_LIST = {
    '.git', '.idea', '.vscode', '__pycache__', 'venv', '.env', 
    'deploy.py', '.DS_Store', 'tmp', 'tests', 'docs'
}

def create_remote_dir(sftp, remote_directory):
    """Recursively creates remote directories."""
    if remote_directory == '/':
        sftp.chdir('/')
        return
    if remote_directory == '':
        return
    
    try:
        sftp.chdir(remote_directory)
    except IOError:
        dirname, basename = os.path.split(remote_directory.rstrip('/'))
        create_remote_dir(sftp, dirname)
        try:
            sftp.mkdir(basename)
            sftp.chdir(basename)
            print(f"Created remote directory: {remote_directory}")
        except IOError as e:
            print(f"Error creating directory {remote_directory}: {e}")
            return

def deploy():
    if not all([HOST, USERNAME, PASSWORD]):
        print("Error: Missing environment variables.")
        print("Please set DEPLOY_HOST, DEPLOY_USER, and DEPLOY_PASSWORD.")
        sys.exit(1)

    print(f"Connecting to {HOST}:{PORT} as {USERNAME}...")
    
    transport = paramiko.Transport((HOST, PORT))
    try:
        transport.connect(username=USERNAME, password=PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        print(f"Starting deployment to {REMOTE_PATH}...")
        
        # Ensure base remote path exists
        try:
            sftp.stat(REMOTE_PATH)
        except IOError:
            print(f"Remote path {REMOTE_PATH} does not exist. Creating...")
            create_remote_dir(sftp, REMOTE_PATH)

        local_path = os.getcwd()
        
        # Walk through local directory
        for root, dirs, files in os.walk(local_path):
            # Filter ignore directories
            dirs[:] = [d for d in dirs if d not in IGNORE_LIST]
            
            rel_path = os.path.relpath(root, local_path)
            if rel_path == '.':
                rel_path = ''
                
            remote_dir = os.path.join(REMOTE_PATH, rel_path).replace('\\', '/')
            
            # Create directory on remote if it doesn't exist
            try:
                sftp.stat(remote_dir)
            except IOError:
                create_remote_dir(sftp, remote_dir)

            for file in files:
                if file in IGNORE_LIST:
                    continue
                    
                local_file_path = os.path.join(root, file)
                remote_file_path = os.path.join(remote_dir, file).replace('\\', '/')
                
                # Check if file needs to be uploaded
                should_upload = True
                try:
                    remote_stat = sftp.stat(remote_file_path)
                    local_stat = os.stat(local_file_path)
                    
                    # If size matches and remote is newer or same age, skip
                    # Allow 1 second difference for clock skew
                    if (remote_stat.st_size == local_stat.st_size and 
                        remote_stat.st_mtime >= local_stat.st_mtime - 1):
                        should_upload = False
                except IOError:
                    # Remote file does not exist
                    should_upload = True

                if should_upload:
                    print(f"Uploading {file} -> {remote_file_path}")
                    sftp.put(local_file_path, remote_file_path)
                    # Preserve modification time
                    os.utime(local_file_path, None) # touch local to ensure sync
                    sftp.utime(remote_file_path, (int(os.path.getatime(local_file_path)), int(os.path.getmtime(local_file_path))))
                else:
                    # Optional: uncomment to see skipped files
                    # print(f"Skipping {file} (up to date)")
                    pass

        print("Deployment completed successfully!")
        
    except Exception as e:
        print(f"An error occurred during deployment: {e}")
    finally:
        if 'sftp' in locals():
            sftp.close()
        transport.close()

if __name__ == "__main__":
    deploy()
