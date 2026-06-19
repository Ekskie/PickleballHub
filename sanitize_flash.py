import os
import re

app_dir = 'c:/Users/Denn/Desktop/PickleballHub/app'
for root, dirs, files in os.walk(app_dir):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple regex to replace flash(f'...{e}...', 'error') with generic message
            new_content = re.sub(r"flash\(f['\"](.*?){\s*(?:e|err|error|str\(e\)|ae)\s*}(.*?)['\"],\s*['\"]error['\"]\)", r"flash('An error occurred. Please try again.', 'error')", content)
            
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f'Sanitized errors in {filepath}')
