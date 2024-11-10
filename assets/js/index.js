import {
    Configuration,
    Element,
    ElementManager,
    Style,
    I18NManager,
    Router,
    createElement,
    SVGContainers,
    User,
    Modal,
    InputElement,
    Utils,
    Progressbar,
    calcElementHeight
} from './common.js'
import './config.js'

const $configuration = new Configuration();
const $ElementManager = new ElementManager();
const $style = new Style($configuration);
const $i18n = new I18NManager();
const $router = new Router("/pages");
const $modal = new Modal();
const $title = document.title
const $progressbar = new Progressbar()
class SideMenu extends Element {
    constructor() {
        super("aside")
        this._menus = {}
        this._menuButtons = {}
        $style.addAll({
            "aside": {
                "width": "220px",
                "height": "100%",
                "padding-left": "20px",
                "background": "var(--background)",
                "overflow-y": "auto",
                "border-right": "1px solid var(--color)",
                "transform": "translateX(0%)",
                "transition": "transform 150ms cubic-bezier(0.4, 0, 0.2, 1);"
            },
            "aside.hidden": {
                "transform": "translateX(-100%)"
            }
        })
        //
    }
    // split "." for submenu
    // the submenu doesn't have a icon
    // but the parent must contain and then can add submenu
    add(name, icon, handler) {
        const [main, submenu] = name.split(".", 1)
        if (!this._menus[main]) {
            this._menus[main] = {
                icon: null,
                handler: handler,
                submenu: {}
            }
        }
        if (submenu) {
            this._menus[main].submenu[submenu] = {
                handler: handler
            }
        } else {
            this._menus[main].handler = handler
        }
    }
    renderButtons() {
        const buttons = [];
        foreach (k in this._menus)
    }
    clear() {

    }
    toggle() {
        this.hasClasses("hidden") ? this.removeClasses("hidden") : this.classes("hidden")
    }
}
$style.setTheme("light", {
    "main-color": "#ffffff",
    "color": "#000000",
    "background": "#F5F6F8"
})
$style.setTheme("dark", {
    "main-color": "#000000",
    "color": "#ffffff",
    "background": "#181818"
})
$style.addAll({
    "::-webkit-scrollbar, html ::-webkit-scrollbar": {
        "width": "5px",
        "height": "5px",
        "border-radius": "10px"
    },
    "::-webkit-scrollbar-thumb, html ::-webkit-scrollbar-thumb": {
        "box-shadow": "rgba(0, 0, 0, 0) 0px 0px 6px inset",
        "background-color": "rgb(102, 102, 102)",
        "border-radius": "10px",
    },
    "body,html": {
        "margin": "0",
        "padding": 0,
    },
    "*": {
        "box-sizing": "border-box",
        "font-family": "Segoe UI, sans-serif"
    },
    "body": {
        "overflow": "hidden"
    },
    ".app": {
        "height": "100vh",
        "width": "100vw",
        "background": "var(--background)",
        "overflow-y": "auto"
    },
    "header": `
        background-color: var(--background);
        text-align: center;
        min-height: 56px;
        width: 100%;
        padding: 8px;
        position: fixed;
        z-index: 1;
        display: flex;
        align-items: center;
        flex-wrap: nowrap;
        justify-content: space-between
    `,
    "header .content": {
        "display": "flex",
        "align-items": "center"
    },
    "header svg": {
        "width": "48px",
        "height": "48px",
        "padding": "8px", 
        "cursor": "pointer"
    },
    "h1,h2,h3,h4,h5,h6": "margin:0;color:var(--color)",
    "svg": {
        "fill": "var(--color)"
    },
    "container": {
        "position": "relative",
        "top": "64px",
        "display": "flex",
        "flex-direction": "row",
        "flex-wrap": "nowrap",
    },
    "main": {
    }
})
function load() {
    const $dom_body = new Element(document.body);

    const $app = createElement("div").classes("app")
    const $header = createElement("header")
    const $theme = {
        sun: SVGContainers.sun,
        moon: SVGContainers.moon
    }
    for (const $theme_key in $theme) {
        $theme[$theme_key].addEventListener("click", () => {
            $header_content_left.children[0].removeChild($theme[$theme_key]);
            $style.applyTheme($theme_key == "sun" ? "light" : "dark");
            $header_content_left.children[0].append($theme[$theme_key == "sun" ? "moon" : "sun"]);
            $configuration.set("theme", $theme_key == "sun" ? "light" : "dark");
        })
    }
    const $header_content_left = createElement("div").classes("content").append(
        createElement("div").append(
            SVGContainers.menu.addEventListener("click", () => {
                $aside.toggle();
            }),
            $theme[$configuration.get("theme") == "light" ? "moon" : "sun"]
        ),
        createElement("h3").text("Python OpenBMCLAPI Dashboard")
    );
    const $header_content_right = createElement("div");
    $header.append($header_content_left, $header_content_right);

    const $container = createElement("container");
    const $main = createElement("main");
    const $aside = new SideMenu()

    $app.append($progressbar, $header, $container.append(
        $aside,
        $main
    ));

    $dom_body.appendBefore($app);

    const observer = new ResizeObserver((..._) => {
        var header = calcElementHeight($header)
        var height = window.innerHeight - header
        $container.style("height", `${height}px`)
    });
    observer.observe($app.origin, { childList: true, subtree: true });
}
window.addEventListener("DOMContentLoaded", () => {
    load()
    Array.from(document.getElementsByClassName("preloader")).forEach(e => {
        const element = new Element(e);
        requestAnimationFrame(() => {
            element.classes("hidden");
            setTimeout(() => {
                element.remove();
            }, 1000)
        })
    })
})
