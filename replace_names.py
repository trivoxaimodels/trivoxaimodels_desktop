import os
import glob

replacements = {
    "ImageTo3D Pro": "Trivox AI Models",
    "ImageTo3DPro": "TrivoxAIModels",
    "imageto3dpro-4f1j.onrender.com": "trivoxaimodels-r5ip.onrender.com"
}

directories = ["core", "ui", "config", "inference", "hooks", "."]
extensions = [".py", ".md", ".spec", ".example", ".yaml"]

def perform_replacements():
    count = 0
    for d in directories:
        for ext in extensions:
            pattern = os.path.join(d, f"*{ext}")
            for filepath in glob.glob(pattern):
                if not os.path.isfile(filepath) or filepath.endswith("replace_names.py"):
                    continue
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    new_content = content
                    for old, new in replacements.items():
                        new_content = new_content.replace(old, new)

                    if content != new_content:
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        print(f"Updated: {filepath}")
                        count += 1
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    # Also handle subdirectories manually since glob is not recursive without **
    for root, dirs, files in os.walk("."):
        if ".git" in root or "venv" in root or "__pycache__" in root:
            continue
        for file in files:
            if not any(file.endswith(ext) for ext in extensions):
                continue
            if file == "replace_names.py":
                continue
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                new_content = content
                for old, new in replacements.items():
                    new_content = new_content.replace(old, new)

                if content != new_content:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"Updated via walk: {filepath}")
                    count += 1
            except Exception as e:
                pass
    print(f"Total files updated: {count}")

if __name__ == "__main__":
    perform_replacements()
