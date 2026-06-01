import os
import re

def add_table_responsive(dir_path):
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Check if there is a table that isn't wrapped
                # Note: this is a simple regex replacement
                # We find <table ...> and </table>, and wrap them in <div class="table-responsive"> if not already wrapped
                
                # Split content by </table>
                if '<table ' in content and 'class="crm-table' in content:
                    if '<div class="table-responsive">' not in content:
                        print('Fixing:', file_path)
                        content = re.sub(r'(<table[^>]*class="[^"]*crm-table[^"]*"[^>]*>.*?</table>)', r'<div class="table-responsive">\n\1\n</div>', content, flags=re.DOTALL)
                        
                        if content != original_content:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)

add_table_responsive('templates')
print('Tables fixed')
