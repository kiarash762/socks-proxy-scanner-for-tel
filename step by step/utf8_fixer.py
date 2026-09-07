import sys
import os

def fix_encoding_error(file_path, output_path=None):
    # List of possible encodings (in order of priority)
    encodings = ['utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'cp1252', 'latin-1']
    content = None
    used_encoding = None

    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read()
                used_encoding = enc
                break
        except UnicodeDecodeError:
            continue

    # If none of the encodings worked, fallback to latin-1 (always succeeds)
    if content is None:
        with open(file_path, 'rb') as f:
            raw = f.read()
            content = raw.decode('latin-1')
            used_encoding = 'latin-1'

    print(f"File successfully read with encoding '{used_encoding}'.")

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Content saved as UTF-8 to '{output_path}'.")
    else:
        # Show a preview of the content
        preview = content[:500]
        if len(content) > 500:
            preview += "..."
        print("Content preview:")
        print(preview)

if __name__ == "__main__":
    # Ask user for input filename
    input_file = input("Please enter the filename to fix (e.g., 62.220.126.56.txt): ").strip()
    
    if not input_file:
        print("No filename provided. Exiting.")
        sys.exit(1)
    
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found.")
        sys.exit(1)
    
    # Ask whether to save the fixed version
    save_choice = input("Do you want to save the fixed version as UTF-8? (y/n): ").strip().lower()
    
    output_file = None
    if save_choice == 'y':
        default_output = f"fixed_{input_file}"
        output_file = input(f"Enter output filename (default: {default_output}): ").strip()
        if not output_file:
            output_file = default_output
    
    fix_encoding_error(input_file, output_file)
    
    if not output_file:
        print("No output file saved. To save, run again and choose 'y'.")