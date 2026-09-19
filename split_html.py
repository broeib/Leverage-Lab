import re

with open("dashboard/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# Extract styles
style_match = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
if style_match:
    styles = style_match.group(1).strip()
    with open("dashboard/css/styles.css", "w", encoding="utf-8") as f:
        f.write(styles)

# Extract scripts
# The main script starts at line 1353, we need to make sure we get the correct one.
# It's the last script tag.
script_match = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
if script_match:
    app_js = script_match[-1].strip()
    with open("dashboard/js/app.js", "w", encoding="utf-8") as f:
        f.write(app_js)

# Now modify the html
new_content = re.sub(r'<style>.*?</style>', '<link rel="stylesheet" href="css/styles.css">', content, flags=re.DOTALL)
new_content = re.sub(r'<script>(.*?)</script>', '', new_content, flags=re.DOTALL)
# Add the script link right before </body>
new_content = new_content.replace('</body>', '    <script src="js/app.js"></script>\n</body>')

with open("dashboard/index.html", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Split completed successfully!")
