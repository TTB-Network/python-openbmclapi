import json
import traceback
from .config import ROOT_PATH, cfg
import string

class I18n:
    def __init__(self, lang: str):
        self.lang = lang
        self.translations: dict[str, string.Template] = {}
        self.load()

    def load(self):
        try:
            with open(ROOT / f'{self.lang}.json', 'r', encoding='utf-8') as f:
                self.translations = {
                    key: string.Template(value) for key, value in json.load(f).items()
                }
        except:
            print(f'[Language] Failed to load language {self.lang}')
            print(traceback.format_exc())

ROOT = ROOT_PATH / 'locale'
languages: dict[str, I18n] = {}
lang: str = cfg.get('advanced.locale') or 'zh_cn'

def t(key: str, *args, **kwargs):
    if lang not in languages or key not in languages[lang].translations:
        return key
    return languages[lang].translations[key].safe_substitute(*args, **kwargs)

def load_languages():
    for file in ROOT.glob('*.json'):
        lang = file.stem
        languages[lang] = I18n(lang)
        languages[lang].load()