import os
from pathlib import Path
import datetime

def combine_python_files(start_path: str, output_file: str) -> None:
    """
    Recursively find all Python files in the given directory and combine them into a single text file.
    Each file's content will be preceded by its path as a header.
    
    Args:
        start_path: The directory to start searching from
        output_file: The name of the output file
    """
    # Convert to absolute path
    start_path = os.path.abspath(start_path)
    
    # Initialize counter for files processed
    files_processed = 0
    
    try:
        with open(output_file, 'w', encoding='utf-8') as outfile:
            # Write header with timestamp
            outfile.write(f"# Combined Python Codebase\n")
            outfile.write(f"# Generated on: {datetime.datetime.now()}\n")
            outfile.write(f"# Source directory: {start_path}\n\n")
            
            # Walk through directory=
            for root, dirs, files in os.walk(start_path):
                # Skip __pycache__ and virtual environment directories
                dirs[:] = [d for d in dirs if d not in ['__pycache__', 'venv', '.venv', '.git']]
                
                # Process Python files
                for file in files:
                    # if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, start_path)
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8') as infile:
                                # Write file header
                                outfile.write(f"\n{'='*80}\n")
                                outfile.write(f"# File: {relative_path}\n")
                                outfile.write(f"{'='*80}\n\n")
                                
                                # Write file content
                                outfile.write(infile.read())
                                outfile.write("\n")
                                
                                files_processed += 1
                                
                        except Exception as e:
                            outfile.write(f"# Error reading file {relative_path}: {str(e)}\n")
            
            # Write summary at the end
            outfile.write(f"\n{'='*80}\n")
            outfile.write(f"# Summary: Processed {files_processed} Python files\n")
            outfile.write(f"# End of combined codebase\n")
            
        print(f"Successfully combined {files_processed} Python files into {output_file}")
        print(f"Output file size: {os.path.getsize(output_file) / 1024:.2f} KB")
        
    except Exception as e:
        print(f"Error writing to output file: {str(e)}")

if __name__ == "__main__":
    current_dir = os.getcwd()
    current_dir = "/home/admin/Plus91Backoffice/plus91_management/app/models"
    output_file = "combined_codebase.txt"
    
    combine_python_files(current_dir, output_file)
