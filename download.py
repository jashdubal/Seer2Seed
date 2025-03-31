import libtorrent as lt
import time
import sys
import os
import re
import signal

# Global variable to track the active session and handle
active_session = None
active_handle = None

def signal_handler(sig, frame):
    """Handle interrupt signals gracefully"""
    print("\n\nInterrupt received, shutting down gracefully...")
    
    if active_session is not None and active_handle is not None:
        print("Stopping torrent and closing session...")
        # Pause the torrent to stop network activity
        active_handle.pause()
        # Save resume data for potential future resuming
        active_handle.save_resume_data()
        # Wait briefly for the resume data to be processed
        time.sleep(1)
        # Remove the torrent but keep the files
        active_session.remove_torrent(active_handle)
    
    print("Shutdown complete. Exiting.")
    sys.exit(0)

def get_known_extensions():
    """Return a list of known safe file extensions"""
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
    subtitle_extensions = ['.srt', '.ass', '.sub', '.idx', '.sup']
    audio_extensions = ['.mp3', '.wav', '.flac', '.ogg', '.aac', '.m4a']
    document_extensions = ['.pdf', '.epub', '.mobi', '.doc', '.docx', '.txt']
    archive_extensions = ['.zip', '.rar', '.7z', '.tar', '.gz']
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
    
    return video_extensions + subtitle_extensions + audio_extensions + document_extensions + archive_extensions + image_extensions

def check_torrent_name(name):
    """
    Check if the torrent name is acceptable
    
    Args:
        name (str): Name of the torrent
        
    Returns:
        tuple: (is_acceptable, reason) - Boolean indicating if acceptable and reason if not
    """
    # TODO: Implement name checking logic
    # This is a placeholder function - implement your own logic here
    
    # Example implementation:
    # if "malware" in name.lower():
    #     return False, "Torrent name contains suspicious keywords"
    
    return True, "Torrent name passed checks"

def is_safe_torrent(handle):
    """
    Validate if a torrent is safe to download based on various checks
    
    Args:
        handle: Torrent handle with metadata
        
    Returns:
        tuple: (is_safe, reason) - Boolean indicating if safe and reason if not
    """
    # Wait for metadata if needed
    while not handle.status().has_metadata:
        time.sleep(1)
        print("\rWaiting for metadata...", end='')
    
    print("\rValidating torrent safety...", end='')
    
    # Get torrent info
    info = handle.torrent_file()
    
    # Check 1: File size (e.g., > 50GB might be suspicious)
    total_size = info.total_size()
    if total_size > 50 * 1024 * 1024 * 1024:  # 50GB
        return False, f"Torrent size is suspiciously large: {total_size / (1024**3):.2f} GB"
    
    # Check 2: Too many small files (could be a sign of malware)
    small_files_count = 0
    for i in range(info.num_files()):
        if info.files().file_size(i) < 10 * 1024:  # Less than 10KB
            small_files_count += 1
    
    if small_files_count > 100:  # Arbitrary threshold
        return False, f"Contains suspiciously many small files: {small_files_count}"
    
    # Check 3: Torrent name check
    torrent_name = info.name()
    name_safe, name_reason = check_torrent_name(torrent_name)
    if not name_safe:
        return False, name_reason
    
    return True, "Torrent passed safety checks"

def filter_files_by_extension(handle):
    """
    Set file priorities to only download files with known extensions
    
    Args:
        handle: Torrent handle with metadata
        
    Returns:
        tuple: (total_files, selected_files) - Counts of total and selected files
    """
    known_extensions = get_known_extensions()
    
    # Wait for metadata if needed
    while not handle.status().has_metadata:
        time.sleep(1)
    
    info = handle.torrent_file()
    file_priorities = []
    total_files = info.num_files()
    selected_files = 0
    skipped_extensions = set()
    
    print("\nSelecting files to download:")
    
    for i in range(total_files):
        file_path = info.files().file_path(i)
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext in known_extensions:
            file_priorities.append(4)  # Normal priority
            selected_files += 1
            print(f"✓ Will download: {file_path}")
        else:
            file_priorities.append(0)  # Don't download
            skipped_extensions.add(file_ext)
            print(f"✗ Skipping: {file_path}")
    
    handle.prioritize_files(file_priorities)
    
    if skipped_extensions:
        print(f"\nSkipped file types: {', '.join(skipped_extensions)}")
    
    return total_files, selected_files

def download_torrent(magnet_link, save_path="./downloads"):
    """
    Download a torrent from a magnet link
    
    Args:
        magnet_link (str): Magnet link to download
        save_path (str): Directory to save the downloaded files
    """
    global active_session, active_handle
    
    # Create session with appropriate settings
    settings = {
        'enable_dht': True,
        'enable_lsd': True,
        'enable_upnp': True,
        'enable_natpmp': True,
        'alert_mask': lt.alert.category_t.all_categories
    }
    
    ses = lt.session(settings)
    active_session = ses
    
    # Parse magnet link
    params = lt.parse_magnet_uri(magnet_link)
    
    # Create a temporary save path to get metadata
    temp_save_path = save_path
    params.save_path = temp_save_path
    
    # Add the torrent to the session
    handle = ses.add_torrent(params)
    active_handle = handle
    
    # Wait for metadata
    print(f"Downloading metadata...")
    while not handle.status().has_metadata:
        print("\rWaiting for metadata...", end='')
        time.sleep(1)
    
    print("\nMetadata received!")
    
    # Get torrent name for folder creation
    torrent_name = handle.status().name
    
    # Create folder for this specific torrent
    torrent_folder = os.path.join(save_path, torrent_name)
    os.makedirs(torrent_folder, exist_ok=True)
    
    # Update save path to the torrent-specific folder
    handle.move_storage(torrent_folder)
    
    # Validate torrent safety
    is_safe, reason = is_safe_torrent(handle)
    
    if not is_safe:
        print(f"Safety check failed: {reason}")
        print("Aborting download for safety reasons.")
        ses.remove_torrent(handle)
        return
    
    print(f"Safety check passed: {reason}")
    
    # Filter files by extension
    total_files, selected_files = filter_files_by_extension(handle)
    
    if selected_files == 0:
        print("No files with known safe extensions found in this torrent.")
        print("Aborting download for safety reasons.")
        ses.remove_torrent(handle)
        return
    
    print(f"\nDownloading {selected_files} of {total_files} files from: {torrent_name}")
    
    # Monitor the download progress
    while handle.status().state != lt.torrent_status.seeding:
        status = handle.status()
        
        # Calculate download progress
        progress = status.progress * 100
        download_rate = status.download_rate / 1000  # KB/s
        
        state_str = ['queued', 'checking', 'downloading metadata', 
                    'downloading', 'finished', 'seeding', 'allocating']
        
        current_state = state_str[status.state] if status.state < len(state_str) else "unknown"
        
        print(f"\rStatus: {current_state} | "
              f"Progress: {progress:.2f}% | "
              f"Download speed: {download_rate:.2f} KB/s | "
              f"Peers: {status.num_peers}", end='')
        
        time.sleep(1)
    
    print("\nDownload complete!")

def get_magnet_link():
    """Get a magnet link from the user"""
    while True:
        magnet_link = input("Enter magnet link: ").strip()
        
        if not magnet_link:
            print("Magnet link cannot be empty. Please try again.")
            continue
            
        if not magnet_link.startswith('magnet:'):
            print("Error: Only magnet links are supported. Links should start with 'magnet:'")
            continue
            
        # Basic validation of magnet link format
        if not re.search(r'xt=urn:btih:[a-zA-Z0-9]{32,40}', magnet_link):
            print("Error: Invalid magnet link format. Please check and try again.")
            continue
            
        return magnet_link

if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    try:
        # Interactive mode if no arguments provided
        if len(sys.argv) < 2:
            magnet_link = get_magnet_link()
            save_path = input("Enter save path (or press Enter for './downloads'): ").strip() or "./downloads"
        else:
            magnet_link = sys.argv[1]
            
            if not magnet_link.startswith('magnet:'):
                print("Error: Only magnet links are supported")
                sys.exit(1)
                
            save_path = sys.argv[2] if len(sys.argv) > 2 else "./downloads"
        
        # Create save directory if it doesn't exist
        os.makedirs(save_path, exist_ok=True)
        download_torrent(magnet_link, save_path)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        # Attempt to clean up if an exception occurs
        if active_session is not None and active_handle is not None:
            active_session.remove_torrent(active_handle)
        sys.exit(1)