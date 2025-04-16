import os
import datetime

def print_directory_tree(start_path: str, output_file: str = None, exclude: list = None):
    """
    Print or write the directory structure starting from the given directory in a tree-like format.
    
    Args:
        start_path: The root directory to start from.
        output_file: Optional; if provided, write the output to this file instead of printing to console.
        exclude: Optional; list of directory names to exclude from the traversal.
    """
    # Validate the starting path
    if not os.path.exists(start_path):
        print(f"Error: Path '{start_path}' does not exist.")
        return
    if not os.path.isdir(start_path):
        print(f"Error: '{start_path}' is not a directory.")
        return
    
    # Set default exclude list if none provided
    if exclude is None:
        exclude = ['__pycache__', 'venv', '.venv', '.git']
    
    # Helper function to recursively print the directory tree
    def _print_tree(path, prefix, file):
        try:
            # Get directory contents, excluding specified directories
            contents = [entry for entry in os.scandir(path) if entry.name not in exclude]
        except Exception as e:
            print(f"{prefix}└── [Error: {str(e)}]", file=file)
            return
        
        # Sort contents alphabetically for consistent output
        contents.sort(key=lambda e: e.name)
        
        # Process each entry in the directory
        for i, entry in enumerate(contents):
            # Determine if this is the last item to choose the connector
            is_last = i == len(contents) - 1
            connector = '└── ' if is_last else '├── '
            
            # Print the current entry
            print(f"{prefix}{connector}{entry.name}", file=file)
            
            # If it's a directory, recurse into it with updated prefix
            if entry.is_dir():
                new_prefix = prefix + ('    ' if is_last else '│   ')
                _print_tree(entry.path, new_prefix, file)
    
    # Determine output method and write header
    header = (
        f"# Directory Structure\n"
        f"# Generated on: {datetime.datetime.now()}\n"
        f"# Source directory: {os.path.abspath(start_path)}\n\n"
    )
    
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(header)
                _print_tree(start_path, '', f)
            print(f"Directory structure written to '{output_file}'")
        except Exception as e:
            print(f"Error writing to '{output_file}': {str(e)}")
    else:
        print(header.rstrip())  # Remove trailing newline for console output
        _print_tree(start_path, '', None)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python script.py <directory> [output_file]")
        sys.exit(1)
    
    start_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    print_directory_tree(start_path, output_file)