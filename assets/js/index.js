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
    calcElementWidth,
    Utils,
    ObjectID,
    ref
} from './common.js'

import './config.js'

class Menu extends Element {
    constructor() {
        super("div").classes("menu-side")
        $style.addAll({
            ".menu-side": {
                "position": "absolute",
                "width": "232px",
                "height": "100%",
                "padding": "16px 16px 0px 24px",
                "background": "var(--background)",
                "transition": "transform 500ms cubic-bezier(0, 0, 0.2, 1), opacity 500ms cubic-bezier(0, 0, 0.2, 1)",
                "transform": "translateX(0%)",
                "opacity": "1",
                "z-index": "999"
            },
            ".menu-main": {
                "margin-left": "216px",
                "transition": "margin-left 500ms cubic-bezier(0, 0, 0.2, 1)",
            },
            "@media (max-width: 600px)": {
                ".menu-main": {
                    "margin-left": "0px"
                }
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

    async send(event, data) {
        if (this.support_websocket) return this._ws_send(event, data);
        return this._http_send(event, data);
    }

    get support_websocket() {
        return window.__CONFIG__.support.websocket;
    }
}

class SwitchElement extends Element {
    constructor() {
        super("div").classes("switch-container");
        this._buttons = [];
        this.$buttons = [];
        this._render_task = null;
        this.$bar = createElement("span").classes("switch-bar");
        this.$main = createElement("div").classes("switch-main")
        this.append(this.$main.append(
            this.$bar
        ))
        this.select(-1)

        $style.addAll({
            ".switch-container": `
                position: relative;
                display: inline-block;
                flex: 1 1 auto;
                white-space: nowrap;
                overflow-x: hidden;
                width: 100%;
            `,
            ".switch-main": {
                "display": "flex",
            },
            ".switch-bar": {
                "position": "absolute",
                "height": "100%",
                "border-radius": "4px",
                "background": "var(--main-color)",
                "transition": "300ms cubic-bezier(0.4, 0, 0.2, 1)"
            },
            ".switch-button": `
                display: inline-flex;
                -webkit-box-align: center;
                align-items: center;
                -webkit-box-pack: center;
                justify-content: center;
                box-sizing: border-box;
                -webkit-tap-highlight-color: transparent;
                background-color: transparent;
                outline: 0px;
                border: 0px;
                margin: 0px;
                border-radius: 0px;
                cursor: pointer;
                user-select: none;
                vertical-align: middle;
                appearance: none;
                text-decoration: none;
                font-family: inherit;
                font-weight: 500;
                line-height: 1.25;
                text-transform: uppercase;
                max-width: 360px;
                position: relative;
                flex-shrink: 0;
                overflow: hidden;
                white-space: normal;
                text-align: center;
                flex-direction: column;
                color: var(--text-dark-color);
                z-index: 1;
                padding: 4px 12px;
                min-height: 0px;
                min-width: 0px;
                font-size: 12px;
            `,
            ".switch-button:hover": {
                "color": "var(--main-color)",
            },
            ".switch-button.active": {
                "color": "var(--dark-color)",
            }
        })
        this.index = null;
        this._render_next_index = null;
    }
    addButtons(...button) {
        this._buttons.push(...button);
        if (this._render_task) return this;
        this._render_task = requestAnimationFrame(() => {
            this._render();
        })
        return this;
    }
    _render() {
        this._render_task = null;
        for (let button of this.$buttons) {
            button.remove();
        }
        this.$buttons = [];
        for (const button_index in this._buttons) {
            var $button = createElement("button").classes("switch-button").i18n(this._buttons[button_index]).addEventListener("click", () => {
                this.select(button_index);
            });
            this.$buttons.push($button);
        }
        this.$main.append(...this.$buttons)
        if (this._render_next_index != null) {
            requestAnimationFrame(() => {
                this.select(this._render_next_index);
                this._render_next_index = null;
            })
        }
    }
    select(index) {
        if (this._render_task) {
            this._render_next_index = index;
            return this;
        };
        this.index = index;
        var buttons_width = this.$buttons.map(e => calcElementWidth(e));
        var left = 0;
        var width = 0;
        if (index >= 0 && index < this.$buttons.length) {
            left = buttons_width.slice(0, index).reduce((a, b) => a + b, 0);
            width = buttons_width[index];
            this.$buttons.forEach(e => {
                if (e === this.$buttons[index]) {
                    e.classes("active");
                } else {
                    e.removeClasses("active")
                }
            })
        }
        this.$bar.style("left", `${left}px`).style("width", `${width}px`);
        this.origin.dispatchEvent(new CustomEvent("change", {
            detail: {
                index: index,
                button: this.$buttons[index]
            }
        }))
        return this;
    }
}

class FlexElement extends Element {
    constructor() {
        super("div").classes("flex-container")
        $style.addAll({
            ".flex-container": {
                "display": "flex",
                "flex-wrap": "wrap"
            }
        })
        this._render_task = null;
        this.observer = new ResizeObserver(() => {
            if (this._render_task) return;
            this._render_task = requestAnimationFrame(() => {
                this._render_task = null;
                this._render();
            })
        })
        this.$child = null;
        this.$minwidth = null;
        this.observer.observe(this.origin)
    }
    _render() {
        if (!this.$child) return;
        const container_width = calcElementWidth(this);
        var handler = null;
        if (this.$minwidth && this.$minwidth > container_width) {
            handler = (child) => container_width
        } else {
            handler = (child) => this._render_calc_child_width(this.children.length, this.children.indexOf(child), container_width)
        }
        for (const child of this.children) {
            var res = handler(child);
            child.style("width", `${res}px`)
        }
    }
    _render_calc_child_width(total_child, index, container_width) {
        const child = this.$child;
        if (child.length == 1) {
            var val = child[0];
            // if val is number
            if (typeof val === "number") {
                return container_width / val;
            }
            if (val.endsWith("%")) {
                return parseFloat(val.slice(0, -1)) / 100.0 * container_width / total_child;
            }
            return 0;
        }
        // first check if all child is number, or all child is percent
        const is_number = child.every(e => typeof e === "number");
        const is_percent = child.every(e => typeof e === "string" && e.endsWith("%"));
        if (is_number) {
            return child[index >= child.length ? child.length - 1 : index] / total_child * container_width;
        }
        if (is_percent) {
            var total = child.reduce((a, b) => a + parseFloat(b.slice(0, -1)), 0);
            return parseFloat(child[index >= child.length ? child.length - 1 : index].slice(0, -1)) / total * container_width;
        }
        console.error(child, " is not a valid width value");
        return 0;
    }
    child(...values) {
        this.$child = values;
        return this;
    }
    minWidth(value) {
        this.$minwidth = value;
        return this;
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
    "switch.dashboard.basic": "基础统计",
    "switch.dashboard.advanced": "高级统计",
    "menu.dashboard": "数据统计",
    "dashboard.title.runtime": "运行时间",
    "dashboard.value.runtime": "%time%",
    "format.count_time": "%hour% 时 %minute% 分 %second% 秒",
    "format.count_time.day": "%day% 天 %hour% 时 %minute% 分 %second% 秒",
})
$style.setTheme("light", {
    "main-color-r": "15",
    "main-color-g": "198",
    "main-color-b": "194",
    "main-color": "rgb(15, 198, 194)",
    "main-light-color": "rgb(23, 231, 229)",
    "color": "#000000",
    "dark-color": "#FFFFFF",
    "text-dark-color": "rgba(0, 0, 0, 0.7)",
    "background": "rgb(247, 248, 250)",
    "footer-background": "#F0F0F0",
    "background-hover": "#F0F1F3",
    "main-dark-color": "rgb(10, 157, 220)",
    "main-shadow-0-2-color": "rgba(15, 198, 194, 0.2)",
    "main-shadow-0-1-color": "rgba(15, 198, 194, 0.1)",
    "main-button-hover": "rgb(10, 138, 135)",
    "panel-box-shadow": "rgba(145, 158, 171, 0.2) 0px 4px 10px;",
    "panel-color": "rgb(255, 255, 255)",
    "title-color": "rgba(0, 0, 0, 0.5)",
    "value-color": "rgba(0, 0, 0, 0.7)",
})
$style.setTheme("dark", {
    "main-color-r": "244",
    "main-color-g": "209",
    "main-color-b": "180",
    "main-color": "rgb(244, 209, 180)",
    "main-light-color": "rgb(255, 239, 210)",
    "color": "#ffffff",
    "dark-color": "#000000",
    "text-dark-color": "rgba(255, 255, 255, 0.7)",
    "background": "rgb(24, 24, 24);",
    "footer-background": "#202020",
    "background-hover": "#202020",
    "main-dark-color": "rgb(235, 187, 151)",
    "main-shadow-0-2-color": "rgba(244, 209, 180, 0.2)",
    "main-shadow-0-1-color": "rgba(244, 209, 180, 0.1)",
    "panel-box-shadow": "none",
    "panel-color": "rgb(35, 35, 35)",
    "title-color": "rgba(255, 255, 255, 0.5);",
    "value-color": "rgb(255, 255, 255);",
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
$style.addAll({
    ".panel": {
        "background": "var(--panel-color)",
        "border-radius": "4px",
        "box-shadow": "var(--panel-box-shadow)",
        "padding": "24px"
    },
    ".pre-switch-container": {
        "background": "var(--panel-color)",
        "border-radius": "4px",
        "box-shadow": "var(--panel-box-shadow)",
        "padding": "9px",
        "margin-bottom": "8px",
    },
    "main": {
        "margin": "0px 16px"
    },
    ".label-text .title": `
        display: flex;
        margin: 0px 0px 6px;
        font-family: inherit;
        font-weight: 400;
        line-height: 1.5;
        color: var(--title-color);
        font-size: 14px
    `,
    ".label-text .value": `
        margin: 0px;
        font-family: inherit;
        font-weight: 400;
        line-height: 1.5;
        color: var(--value-color);
        font-size: 24px;
    `
})
function createPanel() {
    return createElement("div").classes("panel")
}
function createFlexElement() {
    return new FlexElement()
}
function createText(handler) {
    var title = createElement("p").classes("title")
    var value = createElement("p").classes("value")
    handler({
        title,
        value
    })
    return createElement("div").classes("label-text").append(
        title,
        value
    )
}
function createTextWithRef(params = {
    title_i18n: "",
    value_i18n: "",
    title_variable: () => { },
    value_variable: () => { }
}) {
    return createText((label) => {
        for (const key of [
            "title", 
            "value"
        ]) {
            label[key].i18n(params[key + "_i18n"])
            var obj = ref({}, {
                handler: (args) => {
                    label[key].t18n(args.object)
                }
            })
            var handler = params[key + "_variable"]
            if (!handler) continue;
            try {
                handler(obj)
            } catch (e) {
                console.error(e)
            }
        }
    })
}
function runTask(executor, handler, interval) {
    handler()
    return executor(handler, interval)
}
function formatTime(seconds) {
    var s = Math.floor(seconds % 60)
    var m = Math.floor(seconds / 60 % 60)
    var h = Math.floor(seconds / 3600 % 24)
    var d = Math.floor(seconds / 86400)
    if (d > 0) {
        return $i18n.t("format.count_time_days", {
            day: d.toString().padStart(2, "0"),
            hour: h.toString().padStart(2, "0"),
            minute: m.toString().padStart(2, "0"),
            second: s.toString().padStart(2, "0"),
        })
    }
    return $i18n.t("format.count_time", {
        hour: h.toString().padStart(2, "0"),
        minute: m.toString().padStart(2, "0"),
        second: s.toString().padStart(2, "0"),
    })
}
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
    const $menu_variables = {};
    $menu.add("dashboard", "a", (...args) => {
        if (!$menu_variables.dashboard) {
            $menu_variables.dashboard = {};
        }
        const $dashboard_locals = $menu_variables.dashboard
        if (Object.keys($dashboard_locals).length == 0) {
            $dashboard_locals.container = createElement("div");
            $dashboard_locals.basic = [];
            $dashboard_locals.advanced = [];
            // info
            (() => {
                $dashboard_locals.info = createPanel().append(
                    createFlexElement().append(
                        createTextWithRef({
                            title_i18n: "dashboard.title.runtime",
                            value_i18n: "dashboard.value.runtime",
                            value_variable: (obj) => {
                                $dashboard_locals.runtime = obj
                            }
                        }),
                        createTextWithRef({
                            title_i18n: "dashboard.title.status",
                            value_i18n: "dashboard.value.status",
                            value_variable: (obj) => {
                                $dashboard_locals.status = obj
                            }
                        }),
                    ).child(2).minWidth(680)
                )
                $dashboard_locals.info_runtime = ref({}, {
                    handler: (args) => {
                        const object = args.object;
                        if (!object.finish) return;
                        object.finish = false;
                        clearInterval($dashboard_locals.info_runtime_task)
                        $dashboard_locals.info_runtime_task = runTask(setInterval, () => {
                            const runtime = object.current_time - object.start_time - object.diff / 1000.0 + (+new Date() - object.resp_timestamp) / 1000.0;
                            $dashboard_locals.runtime.time = formatTime(runtime);
                        }, 1000)
                    }
                })
                $dashboard_locals.info_task = runTask(setInterval, async () => {
                    var resp = await $channel.send("runtime", +new Date())
                    var start_time = resp.timestamp - resp.runtime;
                    // time fixed
                    for (const [key, value] of Object.entries({
                        current_time: resp.timestamp,
                        start_time,
                        diff: (+new Date() - resp.browser) / 2,
                        resp_timestamp: +new Date(),
                        finish: true
                    })) {
                        $dashboard_locals.info_runtime[key] = value
                    }
                }, 5000)
            })();
            // basic
            (() => {
                const basic = $dashboard_locals.basic;
                basic.push(
                )
            })();

            $dashboard_locals.pre_switch = createElement("div").classes("pre-switch-container").append(
                new SwitchElement().addButtons("switch.dashboard.basic", "switch.dashboard.advanced").addEventListener("change", (event) => {
                    while ($dashboard_locals.container.firstChild != null) {
                        $dashboard_locals.container.removeChild($dashboard_locals.container.firstChild)
                    }
                    if (event.detail.index == 0) {
                        $dashboard_locals.container.append(
                            ...$dashboard_locals.basic
                        )
                    } else {
                        $dashboard_locals.container.append(
                            ...$dashboard_locals.advanced
                        )
                    }
                }).select(0)
            )
        }
        $main.append(
            $dashboard_locals.info,
            $dashboard_locals.pre_switch,
            $dashboard_locals.container
        )
    })

    $router.before_handler(() => {
        while ($main.firstChild != null) {
            $main.removeChild($main.firstChild)
        }
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
