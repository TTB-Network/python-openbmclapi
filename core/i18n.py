from pathlib import Path
import json
from string import Template
from core.config import Config

lang = Config.get("advanced.language")


class Locale:
    def __init__(self, lang: str):
        self.path = Path(f"./i18n/{lang}.json")
        self.data = {}
        self.load()

    def __getitem__(self, key: str):
        return self.data[key]

    def __contains__(self, key: str):
        return key in self.data

    def load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            d = f.read()
            self.data = json.loads(d)
            f.close()

    def get_string(self, key: str, failed_prompt):
        n = self.data.get(key, None)
        if n != None:
            return n
        if failed_prompt:
            return str(key) + self.t("i18n.prompt.failed")
        return key

    def t(self, key: str, failed_prompt=True, *args, **kwargs):
        localized = self.get_string(key, failed_prompt)
        return Template(localized).safe_substitute(*args, **kwargs)


locale: Locale = Locale(lang)
