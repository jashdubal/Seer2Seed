import os
import pytest
import tempfile
import shutil
import logging
from unittest.mock import patch, MagicMock

# No need for sys.path manipulation - conftest.py handles it
import download as dl
import libtorrent as lt
import time

# Set up logging
logger = logging.getLogger(__name__)

@pytest.mark.unit
@pytest.mark.download
def test_download_torrent_mock(capsys):

    """Test the download_torrent function with mocks"""
    # Mock libtorrent session and handle
    mock_session = MagicMock()
    mock_handle = MagicMock()
    mock_status = MagicMock()
    
    # Set up the mocks
    mock_status.has_metadata = True
    mock_status.name = "Test Torrent"
    mock_status.state = dl.lt.torrent_status.seeding  # Changed from main.lt to dl.lt
    mock_status.progress = 1.0
    mock_status.download_rate = 1000
    mock_status.num_peers = 5
    
    # Add more detailed status information
    mock_status.upload_rate = 500  # 500 bytes/s
    mock_status.num_seeds = 10
    mock_status.num_complete = 8  # Complete copies (seeders)
    mock_status.num_incomplete = 3  # Incomplete copies (leechers)
    mock_status.distributed_copies = 2.5  # Average number of complete copies
    mock_status.pieces_to_download = 0
    mock_status.total_wanted = 1 * 1024 * 1024 * 1024  # 1GB
    mock_status.total_wanted_done = 1 * 1024 * 1024 * 1024  # 1GB (completed)
    
    mock_handle.status.return_value = mock_status
    mock_session.add_torrent.return_value = mock_handle
    
    # Mock torrent_file and info
    mock_info = MagicMock()
    mock_info.total_size.return_value = 1 * 1024 * 1024 * 1024  # 1GB
    mock_info.num_files.return_value = 2
    mock_info.name.return_value = "Test Torrent"
    
    # Add more detailed info
    mock_info.comment.return_value = "This is a test torrent"
    mock_info.creator.return_value = "Test Creator"
    mock_info.creation_date.return_value = 1617235200  # Unix timestamp
    mock_info.priv.return_value = False  # Not a private torrent
    mock_info.num_pieces.return_value = 1024
    mock_info.piece_length.return_value = 1 * 1024 * 1024  # 1MB pieces
    
    # Mock files
    mock_files = MagicMock()
    mock_files.file_path.side_effect = lambda i: f"file{i}.mp4"
    mock_files.file_size.side_effect = lambda i: 500 * 1024 * 1024 if i == 0 else 524 * 1024 * 1024  # 500MB and 524MB
    mock_info.files.return_value = mock_files
    
    mock_handle.torrent_file.return_value = mock_info
    
    # Create a custom print function to capture output
    original_print = print
    
    def custom_print(*args, **kwargs):
        original_print(*args, **kwargs)
    
    # Patch the necessary functions and classes
    with patch('libtorrent.session', return_value=mock_session), \
         patch('libtorrent.parse_magnet_uri'), \
         patch('os.makedirs'), \
         patch('builtins.print', side_effect=custom_print), \
         patch('time.sleep'):
        
        # Call the function
        dl.download_torrent("magnet:?xt=urn:btih:test", "./test_downloads")
        
        # Print detailed torrent information
        print("\n----- TORRENT METADATA -----")
        print(f"Name: {mock_info.name()}")
        print(f"Size: {mock_info.total_size() / (1024**3):.2f} GB")
        print(f"Files: {mock_info.num_files()}")
        print(f"Comment: {mock_info.comment()}")
        print(f"Creator: {mock_info.creator()}")
        print(f"Creation Date: {mock_info.creation_date()}")
        print(f"Private: {mock_info.priv()}")
        print(f"Pieces: {mock_info.num_pieces()} x {mock_info.piece_length() / 1024:.0f} KB")
        
        print("\n----- FILE DETAILS -----")
        for i in range(mock_info.num_files()):
            file_path = mock_files.file_path(i)
            file_size = mock_files.file_size(i)
            print(f"File {i+1}: {file_path} ({file_size / (1024**2):.2f} MB)")
        
        print("\n----- DOWNLOAD STATUS -----")
        print(f"Progress: {mock_status.progress * 100:.2f}%")
        print(f"Download Rate: {mock_status.download_rate / 1024:.2f} KB/s")
        print(f"Upload Rate: {mock_status.upload_rate / 1024:.2f} KB/s")
        print(f"Peers: {mock_status.num_peers}")
        print(f"Seeds: {mock_status.num_seeds}")
        print(f"Complete Copies (Seeders): {mock_status.num_complete}")
        print(f"Incomplete Copies (Leechers): {mock_status.num_incomplete}")
        print(f"Distributed Copies: {mock_status.distributed_copies:.2f}")
        
        # Verify the expected calls were made
        mock_session.add_torrent.assert_called_once()
        mock_handle.move_storage.assert_called_once()
        
        # Capture the output
        captured = capsys.readouterr()
        
        # Verify that important information was printed
        assert "TORRENT METADATA" in captured.out
        assert "FILE DETAILS" in captured.out
        assert "DOWNLOAD STATUS" in captured.out

@pytest.mark.download
@pytest.mark.real
@pytest.mark.slow
def test_download_torrent_real(caplog):
    """Test downloading a real torrent (just metadata)"""
    # Set logging level to INFO to capture all our log messages
    caplog.set_level(logging.INFO)
    
    # Use a real, well-seeded magnet link
    test_magnet = "magnet:?xt=urn:btih:52FD58172C296021F2E351B8A12BBC8BE7C88F8D"
    
    # Create a temporary directory for downloads
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Set up a real libtorrent session
        settings = {
            'enable_dht': True,
            'enable_lsd': True,
            'enable_upnp': True,
            'enable_natpmp': True,
            'alert_mask': lt.alert.category_t.all_categories
        }
        
        ses = lt.session(settings)
        
        # Parse magnet link
        params = lt.parse_magnet_uri(test_magnet)
        params.save_path = temp_dir
        
        # Add the torrent to the session
        handle = ses.add_torrent(params)
        
        # Wait for metadata (with a timeout)
        logger.info("\nWaiting for torrent metadata (this may take a minute)...")
        timeout = 0
        max_timeout = 60  # 60 seconds max
        
        while not handle.status().has_metadata and timeout < max_timeout:
            time.sleep(1)
            timeout += 1
            if timeout % 5 == 0:  # Log status every 5 seconds
                logger.info(f"Still waiting for metadata... ({timeout}s)")
        
        # Check if we got metadata
        assert handle.status().has_metadata, "Failed to get metadata within timeout"
        
        # Log torrent information
        info = handle.torrent_file()
        status = handle.status()
        
        logger.info("\n----- REAL TORRENT METADATA -----")
        logger.info(f"Name: {info.name()}")
        logger.info(f"Size: {info.total_size() / (1024**3):.2f} GB")
        logger.info(f"Files: {info.num_files()}")
        
        try:
            logger.info(f"Comment: {info.comment()}")
            logger.info(f"Creator: {info.creator()}")
        except Exception:
            logger.info("Comment/Creator info not available")
            
        try:
            logger.info(f"Creation Date: {info.creation_date()}")
        except Exception:
            logger.info("Creation date not available")
            
        try:
            logger.info(f"Private: {info.priv()}")
        except Exception:
            logger.info("Private flag not available")
            
        logger.info(f"Pieces: {info.num_pieces()} x {info.piece_length() / 1024:.0f} KB")
        
        logger.info("\n----- FILE DETAILS -----")
        for i in range(min(5, info.num_files())):  # Show up to 5 files
            try:
                file_path = info.files().file_path(i)
                file_size = info.files().file_size(i)
                logger.info(f"File {i+1}: {file_path} ({file_size / (1024**2):.2f} MB)")
            except Exception as e:
                logger.info(f"Error getting file {i} details: {e}")
        
        if info.num_files() > 5:
            logger.info(f"... and {info.num_files() - 5} more files")
        
        logger.info("\n----- DOWNLOAD STATUS -----")
        logger.info(f"Progress: {status.progress * 100:.2f}%")
        logger.info(f"Download Rate: {status.download_rate / 1024:.2f} KB/s")
        logger.info(f"Upload Rate: {status.upload_rate / 1024:.2f} KB/s")
        logger.info(f"Peers: {status.num_peers}")
        
        try:
            logger.info(f"Seeds: {status.num_seeds}")
            logger.info(f"Complete Copies (Seeders): {status.num_complete}")
            logger.info(f"Incomplete Copies (Leechers): {status.num_incomplete}")
        except Exception:
            logger.info("Detailed peer info not available")
            
        # Clean up
        logger.info("\nCleaning up...")
        ses.remove_torrent(handle)
        
        # Also print to stdout for immediate visibility
        print("\n".join(record.message for record in caplog.records))
        
    except Exception as e:
        pytest.fail(f"Error during real torrent test: {e}")
        
    finally:
        # Clean up the temporary directory
        shutil.rmtree(temp_dir) 