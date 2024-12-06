import {
    Configuration,
    Element,
    ElementManager,
    Style,
    I18NManager,
    Router,
    createElement,
    SVGContainers,
    calcElementHeight,
    Utils,
    ObjectID
} from './common.js'

import './config.js'

class Menu extends Element {
    constructor() {
        super("div").classes("menu-side")
        $style.addAll({
            ".menu-side": {
                "position": "absolute",
                "width": "216px",
                "height": "100%",
                "padding-left": "24px",
                "background": "var(--background)",
                "transition": "transform 500ms cubic-bezier(0, 0, 0.2, 1), opacity 500ms cubic-bezier(0, 0, 0.2, 1)",
                "transform": "translateX(0%)",
                "opacity": "1",
                "z-index": "999"
            },
            ".menu-main": {
                "margin-left": "200px",
                "transition": "margin-left 500ms cubic-bezier(0, 0, 0.2, 1)",
            },
            ".menu-side.hidden": {
                "transform": "translateX(-100%)",
                "opacity": "0"
            },
            ".menu-side.hidden ~ .menu-main": {
                "margin-left": "0px",
            },
            ".menu-button": `
                -webkit-tap-highlight-color: transparent;
                background-color: transparent;
                cursor: pointer;
                user-select: none;
                vertical-align: middle;
                appearance: none;
                color: inherit;
                display: flex;
                -webkit-box-flex: 1;
                -webkit-box-pack: start;
                justify-content: flex-start;
                -webkit-box-align: center;
                align-items: center;
                position: relative;
                min-width: 0px;
                box-sizing: border-box;
                text-align: left;
                padding-top: 8px;
                padding-bottom: 8px;
                padding-left: 16px;
                padding-right: 16px;
                height: 46px;
                outline: 0px;
                border-width: 0px;
                border-style: initial;
                border-color: initial;
                border-image: initial;
                margin: 0px 0px 4px;
                text-decoration: none;
                transition: color 150ms cubic-bezier(0.4, 0, 0.2, 1);
                border-radius: 4px;
            `,
            ".menu-button:hover": `
                color: var(--main-color);
            `,
            ".menu-button.active": `
                background-color: var(--main-color);
                color: var(--dark-color);
                box-shadow: rgba(var(--main-color-r), var(--main-color-g), var(--main-color-b), 0.2) 0px 10px 25px 0px;
            `
        })
        this.$menus = {}
        this._render_task = null
        this.route_handler_lock = null;
    }
    toggle() {
        super.toggle("hidden")
    }
    add(type, icon, callback) {
        var path = type.replaceAll(".", "/")
        $router.on(`/${path}`, callback)
        var [main, sub] = type.split(".", 1)
        if (!this.$menus[main]) {
            this.$menus[main] = {
                icon: icon,
                children: []
            }
        }
        this.$menus[main].icon = icon ? icon : this.$menus[main].icon
        if (sub) {
            this.$menus[main].children.push({
                type: sub
            })   
        }
        if (this._render_task) return;
        this._render_task = requestAnimationFrame(() => {
            this._render()
        })
        var cur_key, cur_sub;
        $router.before_handler(async (event) => {
            if (this._render_task) await new Promise((resolve) => {
                this.route_handler_lock = resolve
            })
            var page = event.current_route
            var [key, sub] = page.slice(1).split("/", 2)
            if (cur_key == key && cur_sub == sub) return;
            for (const [$key, $val] of Object.entries(this.$menus)) {
                if ($key.toLocaleLowerCase() != key.toLocaleLowerCase()) {
                    $val.$dom.removeClasses("active")
                    if ($val.$child) $val.$child.removeClasses("hidden")
                    continue
                }
                $val.$dom.classes("active")
                if ($val.$child) $val.$child.classes("hidden")
                console.log($val)
            }
            cur_key = key;
            cur_sub = sub;
        })
    }
    _render() {
        this._render_task = null;
        const menu = this.$menus
        while (this.firstChild != null) this.removeChild(this.firstChild)
        for (const [$key, $val] of Object.entries(menu)) {
            var root = createElement("div").classes("menu-button").append(
                Utils.isDOM($val.icon) || $val.icon instanceof Element ? $val.icon : createElement("div"),
                createElement("p").i18n(`menu.${$key}`),
            ).addEventListener("click", () => {
                $router.page(`/${$key}`)
            })
            this.append(root)
            menu[$key].$dom = root
            if ($val.children.length == 0) continue
            var child = createElement("div")
            for (const $child of $val.children) {
                var children = createElement("div").append(
                    createElement("span"),
                    createElement("p").i18n(`menu.${$key}.${$child.type}`)
                )
                menu[$key].children[$child.type].$dom = children
                child.append(
                    children
                )
            }
            this.append(child)
            root.append(SVGContainers.arrow_down)
            menu[$key].$child = child
        }
        this.route_handler_lock?.()
    }
}

class Channel {
    constructor() {
        this.url = window.location.protocol + "//" + window.location.host + "/api";
        this._http_process = {
            total: 0,
            current: 0,
        };
        if (!this.support_websocket) return;
        this._ws_init();
        this._ws_initizalized = false;
        this._ws_callbacks = {};

        this._ws_send("echo", "cnm").then(e => console.log(e))
    }
    // websocket
    _ws_init() {
        this._ws = new WebSocket("ws" + this.url.slice(4));
        this._ws.onopen = () => {
            this._ws_initizalized = true;
        }
        this._ws.onmessage = (event) => {
            var data = JSON.parse(event.data);
            if (data.echo_id) {
                this._ws_callbacks[data.echo_id].resolve(data.data);
                delete this._ws_callbacks[data.echo_id];
                return;
            }
            console.log(data)
        }
        this._ws.onclose = () => {
            this._ws_initizalized = false;
            this._Ws_reconnect();
        }
        this._ws.onerror = (event) => {
            console.log("websocket error", event)
        }
    }
    _Ws_reconnect() {
        if (this._ws_reconnect_task) return;
        this._ws_reconnect_task = setTimeout(() => {
            this._ws_init();
            this._ws_reconnect_task = null;
        }, 5000)
    }

    async _ws_send(event, data) {
        if (!this._ws_initizalized) return this._http_send(event, data);
        return new Promise(async (resolve, reject) => {
            var echo_id = (await ObjectID.create()).toString();
            this._ws_callbacks[echo_id] = { resolve, reject }
            this._ws.send(JSON.stringify({
                event,
                data,
                echo_id
            }))
        })
    }

    async _http_send(event, data) {
        return new Promise((resolve, reject) => {
            var pushed = false;
            var loaded = 0;
            var current_load = 0;
            var xhr = new XMLHttpRequest();
            xhr.open("POST", this.url);
            xhr.addEventListener("progress", (event) => {
                if (event.lengthComputable) {
                    if (!pushed) return;
                    this._http_process.current -= loaded;
                    this._http_process.total -= event.total;
                    return;
                }
                var diff = event.loaded - current_load;
                loaded += diff;
                current_load = event.loaded;
                this._http_process.current += diff;
                if (pushed) return;
                pushed = true;
                this._http_process.total += event.total;
            })
            xhr.addEventListener("readystatechange", (event) => {
                if (xhr.readyState == 4) {
                    if (xhr.statusText == "OK") {
                        resolve(JSON.parse(xhr.responseText)[0].data)
                    } else {
                        reject(xhr.statusText)
                    }
                }
            })
            xhr.send(JSON.stringify({
                event,
                data: data
            }))
        })
    }

    get support_websocket() {
        return window.__CONFIG__.support.websocket;
    }
}

const $configuration = new Configuration();
const $ElementManager = new ElementManager();
const $style = new Style($configuration);
const $i18n = new I18NManager();
const $router = new Router("/pages");
globalThis.$channel = new Channel();
$i18n.addLanguageTable("zh_CN", {
    "footer.powered_by": "由 %name% 提供服务支持",
})
$style.setTheme("light", {
    "main-color-r": "15",
    "main-color-g": "198",
    "main-color-b": "194",
    "main-color": "rgb(15, 198, 194)",
    "main-light-color": "rgb(23, 231, 229)",
    "color": "#000000",
    "dark-color": "#FFFFFF",
    "background": "#F5F6F8",
    "footer-background": "#F0F0F0",
    "background-hover": "#F0F1F3",
    "main-dark-color": "rgb(10, 157, 220)",
    "main-shadow-0-2-color": "rgba(15, 198, 194, 0.2)",
    "main-shadow-0-1-color": "rgba(15, 198, 194, 0.1)",
    "main-button-hover": "rgb(10, 138, 135)",
})
$style.setTheme("dark", {
    "main-color-r": "244",
    "main-color-g": "209",
    "main-color-b": "180",
    "main-color": "rgb(244, 209, 180)",
    "main-light-color": "rgb(255, 239, 210)",
    "color": "#ffffff",
    "dark-color": "#000000",
    "background": "#181818",
    "footer-background": "#202020",
    "background-hover": "#202020",
    "main-dark-color": "rgb(235, 187, 151)",
    "main-shadow-0-2-color": "rgba(244, 209, 180, 0.2)",
    "main-shadow-0-1-color": "rgba(244, 209, 180, 0.1)"
})
$style.addAll({
    "*": {
        "family": "Sego UI, Roboto, Arial, sans-serif",
    },
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
    "body": {
        "overflow": "hidden"
    },
    ".app": {
        "display": "flex",
        "flex-direction": "column",
        "flex-wrap": "nowrap",
        "justify-content": "space-between",
        "height": "100vh",
        "width": "100vw",
        "background": "var(--background)",
        "overflow-y": "auto",
        "color": "var(--color)"
    },
    "a": {
        "color": "var(--color)",
        "text-decoration": "none"
    },
    "a:hover": {
        "text-decoration": "underline"
    },
    "header": `
        background: var(--background);
        text-align: center;
        min-height: 56px;
        width: 100%;
        padding: 8px 8px 8px 8px;
        z-index: 1;
        display: flex;
        align-items: center;
        flex-wrap: nowrap;
        justify-content: space-between;
        color: var(--color);
        fill: var(--color);
    `,
    "header .content": {
        "display": "flex",
        "align-items": "center"
    },
    "header svg": {
        "width": "48px",
        "height": "48px",
        "padding": "8px", 
        "cursor": "pointer",
        "fill": "inherit"
    },
    "header .padding-left": {
        "padding-left": "8px",
    },
    "h1,h2,h3,h4,h5,h6,p": "margin:0;color:inherit",
    "svg": {
        "fill": "inherit"
    },
    "main": {
        "top": "56px",
        "height": "100%"
        //"overflow": "auto"
    },
    "header.hidden": {
        "display": "none"
    },
    "header.hidden ~ main": {
        "top": "0px"
    },
    "footer": {
        "padding": "24px",
        "flex-direction": "column",
        "background": "var(--footer-background)",
        "color": "var(--color)",
        "display": "flex",
        "align-items": "center",
        "justify-content": "center",
        "index-z": "9999"
    },
})

async function load() {
    const $dom_body = new Element(document.body);
    const $theme = {
        sun: SVGContainers.sun,
        moon: SVGContainers.moon
    }
    const $theme_change = createElement("div").append(
        $theme[$configuration.get("theme") == "light" ? "moon" : "sun"]
    )
    const $header = createElement("header").append(
        createElement("div").classes("content").append(
            createElement("div").append(SVGContainers.menu.addEventListener("click", () => {
                $menu.toggle()
            })),
            createElement("h2").text(document.title)
        ),
        createElement("div").classes("content").append(
            $theme_change
        )
    )
    const $app = createElement("div").classes("app")
    const $container = createElement("div").classes("container")
    const $main = createElement("main")
    const $menu = new Menu()

    $menu.add("dashboard", "a", (...args) => {
        console.log("a")
    })

    for (const $theme_key in $theme) {
        $theme[$theme_key].addEventListener("click", () => {
            $theme_change.removeChild($theme[$theme_key]);
            $style.applyTheme($theme_key == "sun" ? "light" : "dark");
            $theme_change.append($theme[$theme_key == "sun" ? "moon" : "sun"]);
            $configuration.set("theme", $theme_key == "sun" ? "light" : "dark");
        })
    }

    $app.append(
        $header,
        $container.append(
            $menu,
            createElement("div").classes("menu-main").append(
                $main
            )
        )
    )
    $dom_body.append($app)

    const observer = new ResizeObserver((..._) => {
        var header = calcElementHeight($header)
        var height = window.innerHeight - header
        $container.style("height", "auto")
        var container = calcElementHeight($container)
        var height = Math.max(height, container)
        $container.style("height", `${height}px`)
    });
    observer.observe($app.origin, { childList: true, subtree: true });

    $router.init()

}
window.addEventListener("DOMContentLoaded", async () => {
    await load()
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
