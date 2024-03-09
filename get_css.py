import re


with open("css.css", "r", encoding="utf-8") as r:
    content = r.read()
    data = {}
    while '{' in content and '}' in content:
        first = content.find("{")
        second = content.find("}")
        namespace = content[:first].strip()
        code = re.sub(r"/\*[\u0000-\uFFFF]*\*/", "", content[first:second + 1].strip("{}").replace(";\n    ", ";").strip())
        content = content[second + 1:]
        data[namespace] = code
    
    with open("css.json", "w", encoding="utf-8") as w:
        w.write("const extend_default_style = {\n")
        for k, v in data.items():
            w.write(f'    "{k}":"{v}",\n')
        w.write("}")
