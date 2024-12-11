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
                "position": "fixed", 
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
            if (page.length == 1) {
                (() => {
                    const first_menu = Object.values(this.$menus)[0]
                    if (first_menu.children.length != 0) {
                        first_menu.children[0].$dom.click();
                    } else {
                        first_menu.$dom.click();
                    }
                })();
            }
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
        this.timeout = 10000
        if (!this.support_websocket) return;
        this._ws_init();
        this._ws_initizalized = false;
        this._ws_callbacks = {};
        this._ws_timeouts = {}
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
                clearTimeout(this._ws_timeouts[data.echo_id])
                delete this._ws_timeouts[data.echo_id]
                this._ws_callbacks[data.echo_id].resolve(data.data);
                delete this._ws_callbacks[data.echo_id];
                return;
            }
            window.dispatchEvent(new CustomEvent(`channel_${data.event}`, { detail: data.data }))
        }
        this._ws.onclose = () => {
            this._ws_initizalized = false;
            this._ws_reconnect();
        }
        this._ws.onerror = (event) => {
            console.log("websocket error", event)
        }
    }
    _ws_reconnect() {
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
            this._ws_timeouts[echo_id] = setTimeout(() => {
                delete this._ws_callbacks[echo_id];
                reject("timeout")
            }, this.timeout)
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
                    clearTimeout(timer)
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
            var timer = setTimeout(() => {
                xhr.abort();
                reject("timeout")
            }, this.timeout)
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
        this.observer = new ResizeObserver(() => {
            this.select(this.index)
        })
        this.observer.observe(this.origin)
        window.addEventListener("langChange", () => {
            this.select(this.index);
        })
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
        var oldindex = this.index;
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
        if (oldindex == this.index) return this;
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
                "flex-wrap": "wrap",
                "align-items": "flex-start",
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
        this.$autoheight = false;
        this.observer.observe(this.origin)
    }
    _render() {
        if (!this.$child) return;
        const container_width = calcElementWidth(this);
        const container_height = calcElementHeight(this);
        var handler = null;
        var heightHandler = null;
        if (this.$minwidth && this.$minwidth > container_width) {
            handler = (child) => container_width
            heightHandler = (child) => container_height
        } else {
            handler = (child) => this._render_calc_child_width(this.children.length, this.children.indexOf(child), container_width)
            heightHandler = (child) => calcElementHeight(child)
        }
        for (const child of this.children) {
            var res = handler(child);
            child.style("width", `${res}px`)
            if (this.$autoheight) {
                child.style("height", `${heightHandler(child)}px`)
            }
            child.origin.getBoundingClientRect()
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
    autoHeight(value) {
        this.$autoheight = value;
        return this;
    }
}
const EchartType = {
    DATA: 0,
    LABEL: 1
}
class TemplateEchartElement extends Element {
    constructor() {
        super("div")
        this.instance = echarts.init(this.origin)
        this.formatter = this._format_number_unit
        this.type = EchartType.DATA
        this.setOption({
            stateAnimation: {
                duration: 300,
                easing: "cubicOut"
            },
            tooltip: {
                trigger: 'axis',
                formatter: (params) => this._e_templates(params)
            }
        })
    }
    setFormatter(formatter) {
        this.formatter = formatter || this._format_number_unit
        return this
    }
    setOption(option) {
        this.instance.setOption(option)
        var options = {}
        if (!('tooltip' in option && 'formatter' in option['tooltip'])) {
            options.tooltip = {
                ...option['tooltip'],
                formatter: (params) => this._e_templates(params)
            }
        }
        if ('yAxis' in option && !('axisLabel' in option['yAxis'])) {
            options.yAxis = {
                ...option['yAxis'],
                axisLabel: {
                    formatter: (params) => this.formatter(params)
                }
            }
        }
        this.instance.setOption(options)
        return this
    }
    setType(type) {
        this.type = type
        return this
    }
    clear() {
        this.instance.clear()
        return this
    }
    _format_number_unit(n) {
        var d = (n + "").split("."), i = d[0], f = d.length >= 2 ? "." + d.slice(1).join(".") : ""
        return i.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",") + f;
    }
    resize() {
        this.instance.resize()
        return this
    }
    _e_templates(params) {
        const value_formatter = this.formatter
        const data_label = this.type == EchartType.LABEL
        const templates = `<div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;">` + (data_label ? '' : `<span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:{color};"></span>`) + `<span style="font-size:14px;color:#666;font-weight:400;margin-left:2px">{name}</span><span style="float:right;margin-left:20px;font-size:14px;color:#666;font-weight:900">{value}</span><div style="clear:both"></div></div><div style="clear:both"></div></div>`
        var template = ''
        for (const data of (Array.isArray(params) ? params : [params])) {
            let value = isNaN(data.value) ? 0 : data.value
            template += templates.replace("{color}", data.color).replace("{name}", `${data.seriesName}${data_label ? `(${data.data.label})` : ""}`).replace("{value}", value_formatter ? value_formatter(value) : value)
        }
        return `<div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;">` + (data_label ? `` : `<div style="font-size:14px;color:#666;font-weight:400;line-height:1;">${(Array.isArray(params) ? params[0] : params).name}</div>`) + `<div style="margin: ${data_label ? 0 : 10}px 0 0;line-height:1;">${template}</div><div style="clear:both"></div></div><div style="clear:both"></div></div>`
    }
    getOption() {
        return this.instance.getOption()
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
    "format.count_time": "%hour% 时 %minute% 分 %second% 秒",
    "format.count_time.days": "%day% 天 %hour% 时 %minute% 分 %second% 秒",
    "switch.dashboard.storage.:all:": "所有存储",
    "switch.dashboard.storage.alist": "Alist [%path% (%url%)]",
    "switch.dashboard.storage.local": "本地存储 [%path%]",
    "switch.dashboard.storage.webdav": "WebDAV [%path% (%url%)]",
    "unit.hour": "%value% 时",
    "unit.day": "%value% 天",
    "dashboard.title.storage.today.hits": "今日下载数",
    "dashboard.title.storage.today.bytes": "今日下载量",
    "dashboard.title.storage.30days.hits": "30 天下载数",
    "dashboard.title.storage.30days.bytes": "30 天下载量",
    "dashboard.value.storage.hits": "下载数",
    "dashboard.value.storage.bytes": "下载量",
    "dashboard.title.qps": "5 分钟请求数",
    "switch.dashboard.cluster.:all:": "所有节点"

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
    "echarts-color-0": "#0FC6C2",//"#246de6",
    "echarts-color-1": "#6199FE",
    "echarts-color-2": "#FFD268",
    "echarts-color-3": "#FF5576",
    "echarts-color-4": "#89DFE2"
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
    "echarts-color-0": "#F1D6BF",
    "echarts-color-1": "#FFA552", 
    "echarts-color-2": "#F16575", 
    "echarts-color-3": "#65B8FF", 
    "echarts-color-4": "#FF8859"
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
        position: fixed;
        background: var(--background);
        text-align: center;
        min-height: 56px;
        width: 100%;
        padding: 8px 8px 8px 8px;
        z-index: 5;
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
        "padding": "24px",
        //"margin-left": "16px",
        //"margin-bottom": "24px"
    },
    ".pre-panel": {
        "padding-left": "16px",
        "padding-bottom": "24px"
    },
    ".pre-switch-container": {
        "background": "var(--panel-color)",
        "border-radius": "4px",
        "box-shadow": "var(--panel-box-shadow)",
        "padding": "9px",
        "margin-bottom": "24px",
        "margin-left": "16px",
    },
    "main": {
        "padding": "32px 32px 32px 16px",
        "overflow": "auto",
        "height": "calc(100% - var(--height))"
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
class Tools {
    static formatTime(seconds) {
        var s = Math.floor(seconds % 60)
        var m = Math.floor(seconds / 60 % 60)
        var h = Math.floor(seconds / 3600 % 24)
        var d = Math.floor(seconds / 86400)
        return $i18n.t("format.count_time.days", {
            day: d.toString().padStart(2, "0"),
            hour: h.toString().padStart(2, "0"),
            minute: m.toString().padStart(2, "0"),
            second: s.toString().padStart(2, "0"),
        })
    }
    static runTask(executor, handler, interval) {
        handler()
        return executor(handler, interval)
    }
    static createTextWithRef(params = {
        title_i18n: "",
        value_i18n: "",
        title_variable: () => { },
        value_variable: () => { },
        i18n: {}
    }) {
        var i18n = params.i18n || {};
        for (const [lang, val] of Object.entries(i18n)) {
            $i18n.addLanguageTable(lang, val)
        }
        return Tools.createText((label) => {
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
    static createPanel(handler = () => { }) {
        var panel = createElement("div").classes("panel")
        var pre = createElement("div").classes("pre-panel").append(
            panel
        )
        handler({
            panel,
            pre
        })
        return pre
    }
    static createFlexElement() {
        return new FlexElement()
    }
    static createText(handler) {
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
    static formatSimpleNumber(number) {
        // convert number to belike: 100,000, if 100000.0, we are 100,000.0
        return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ", ")
    }
    static _BYTES = {
        "iB": 1,
        "KiB": 1024,
        "MiB": 1024,
        "GiB": 1024,
        "TiB": 1024,
        "PiB": 1024,
        "EiB": 1024,
        "ZiB": 1024,
        "YiB": 1024
    }
    static formatBytes(bytes) {
        var i = 0
        for (const [u, un] of Object.entries(Tools._BYTES).slice(1)) {
            if (bytes / un < 1) {
                break
            }
            bytes /= un
            i += 1
        }
        return `${bytes.toFixed(2)}${Object.keys(Tools._BYTES)[i]}`
    }
    static createEchartElement(handler) {
        var base = new TemplateEchartElement()
        handler({
            echart: base.instance,
            base
        })
        return base
    }
    static formatDate(d) {
        return `${d.getFullYear().toString().padStart(4, "0")}-${(d.getMonth() + 1).toString().padStart(2, "0")}-${d.getDate().toString().padStart(2, "0")}`
    }
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
                $dashboard_locals.info = Tools.createPanel(({ pre, panel }) => {
                    panel.append(
                        Tools.createFlexElement().append(
                            Tools.createTextWithRef({
                                title_i18n: "dashboard.title.runtime",
                                value_i18n: "dashboard.value.runtime",
                                value_variable: (obj) => {
                                    $dashboard_locals.runtime = obj
                                },
                                i18n: {
                                    "zh_CN": {
                                        "dashboard.title.runtime": "运行时间",
                                        "dashboard.value.runtime": "%time%",
                                    }
                                }
                            }),
                            Tools.createTextWithRef({
                                title_i18n: "dashboard.title.status",
                                value_i18n: "dashboard.value.status",
                                value_variable: (obj) => {
                                    $dashboard_locals.status = obj
                                },
                                i18n: {
                                    "zh_CN": {
                                        "dashboard.title.status": "当前状态",
                                        "dashboard.value.status": "正常……？"
                                    }
                                }
                            }),
                        ).child(2).minWidth(680)
                    )
                })
                $dashboard_locals.info_runtime = ref({}, {
                    handler: (args) => {
                        const object = args.object;
                        if (!object.finish) return;
                        object.finish = false;
                        clearInterval($dashboard_locals.info_runtime_task)
                        $dashboard_locals.info_runtime_task = Tools.runTask(setInterval, () => {
                            const runtime = object.current_time - object.start_time - object.diff / 1000.0 + (+new Date() - object.resp_timestamp) / 1000.0;
                            $dashboard_locals.runtime.time = Tools.formatTime(runtime);
                        }, 1000)
                    }
                })
                $dashboard_locals.info_task = Tools.runTask(setInterval, async () => {
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
                $dashboard_locals.files_info = Tools.createPanel(({pre, panel}) => {
                    panel.append(
                        Tools.createFlexElement().append(
                            Tools.createTextWithRef({
                                title_i18n: "dashboard.title.today.hits",
                                value_i18n: "dashboard.value.today.hits",
                                value_variable: (obj) => {
                                    $dashboard_locals.files_info_today_hits = obj;
                                },
                                i18n: {
                                    "zh_CN": {
                                        "dashboard.title.today.hits": "今日下载数",
                                        "dashboard.value.today.hits": "%value%"
                                    }
                                }
                            }),
                            Tools.createTextWithRef({
                                title_i18n: "dashboard.title.today.bytes",
                                value_i18n: "dashboard.value.today.bytes",
                                value_variable: (obj) => {
                                    $dashboard_locals.files_info_today_bytes = obj;
                                },
                                i18n: {
                                    "zh_CN": {
                                        "dashboard.title.today.bytes": "今日下载量",
                                        "dashboard.value.today.bytes": "%value%"
                                    }
                                }
                            }),
                            Tools.createTextWithRef({
                                title_i18n: "dashboard.title.30days.hits",
                                value_i18n: "dashboard.value.30days.hits",
                                value_variable: (obj) => {
                                    $dashboard_locals.files_info_30days_hits = obj;
                                },
                                i18n: {
                                    "zh_CN": {
                                        "dashboard.title.30days.hits": "30 天下载数",
                                        "dashboard.value.30days.hits": "%value%"
                                    }
                                }
                            }),
                            Tools.createTextWithRef({
                                title_i18n: "dashboard.title.30days.bytes",
                                value_i18n: "dashboard.value.30days.bytes",
                                value_variable: (obj) => {
                                    $dashboard_locals.files_info_30days_bytes = obj;
                                },
                                i18n: {
                                    "zh_CN": {
                                        "dashboard.title.30days.bytes": "30 天下载量",
                                        "dashboard.value.30days.bytes": "%value%"
                                    }
                                }
                            }),
                        ).child(4).minWidth(600)
                    )
                })
                $dashboard_locals.system_info = Tools.createPanel(({ panel }) => {
                    panel.append(
                        Tools.createFlexElement().append(
                            Tools.createTextWithRef({
                                title_i18n: "dashboard.title.connection",
                                value_i18n: "dashboard.value.connection",
                                value_variable: (obj) => {
                                    $dashboard_locals.system_info_connection = obj;
                                },
                                i18n: {
                                    "zh_CN": {
                                        "dashboard.title.connection": "连接数",
                                        "dashboard.value.connection": "%value%"
                                    }
                                }
                            }),
                            Tools.createTextWithRef({
                                title_i18n: "dashboard.title.memory",
                                value_i18n: "dashboard.value.memory",
                                value_variable: (obj) => {
                                    $dashboard_locals.system_info_memory = obj;
                                },
                                i18n: {
                                    "zh_CN": {
                                        "dashboard.title.memory": "内存使用",
                                        "dashboard.value.memory": "%value%"
                                    }
                                }
                            }),
                            Tools.createTextWithRef({
                                title_i18n: "dashboard.title.cpu",
                                value_i18n: "dashboard.value.cpu",
                                value_variable: (obj) => {
                                    $dashboard_locals.system_info_cpu = obj;
                                },
                                i18n: {
                                    "zh_CN": {
                                        "dashboard.title.cpu": "处理器使用",
                                        "dashboard.value.cpu": "%value%"
                                    }
                                }
                            }),
                            Tools.createTextWithRef({
                                title_i18n: "dashboard.title.cpu_load",
                                value_i18n: "dashboard.value.cpu_load",
                                value_variable: (obj) => {
                                    $dashboard_locals.system_info_cpu_load = obj;
                                },
                                i18n: {
                                    "zh_CN": {
                                        "dashboard.title.cpu_load": "处理器 5 分钟负载",
                                        "dashboard.value.cpu_load": "%value%"
                                    }
                                }
                            })
                        ).child(4).minWidth(600)
                    )
                })
                const info_collection = createElement("div").append(
                    $dashboard_locals.files_info,
                    $dashboard_locals.system_info
                )
                const section = Tools.createFlexElement().child('70%', '30%').minWidth(1280)
                $dashboard_locals.basic_qps = Tools.createPanel(({ pre, panel }) => {
                    var instance = Tools.createEchartElement(({
                        echart, base
                    }) => {
                        base.style("min-height", "180px")
                        $dashboard_locals.basic_qps_echart = {
                            echart, base
                        };
                    })
                    panel.append(
                        createElement("div").classes("title").append(
                            createElement("div").append(
                                createElement("p").i18n("dashboard.title.qps"),
                                // ...
                            )
                        ),
                        instance
                    )
                    var observer = new ResizeObserver(() => {
                        var width = calcElementWidth(section)
                        if (width < 1280) {
                            pre.style("height", `auto`)
                        } else {
                            pre.style("height", `${calcElementHeight(info_collection)}px`)
                            panel.style("height", "100%")
                        }
                        $dashboard_locals.basic_qps_echart.echart.resize()
                    })
                    observer.observe(info_collection.origin)
                })

                // storage

                $dashboard_locals.storage_switch = new SwitchElement().addButtons("switch.dashboard.storage.:all:").addEventListener("change", (event) => {
                })
                $dashboard_locals.cluster_switch = new SwitchElement().addButtons("switch.dashboard.cluster.:all:").addEventListener("change", (event) => { 
                })
                $dashboard_locals.storage_echarts = {}
                $dashboard_locals.statistics_data = ref({}, {
                    timeout: 20,
                    handler: (object) => {
                        object = object.object;
                        var current = object.current || "total"
                        var data = object[current] || {}
                        for (const [key, values] of Object.entries({
                            "today_hits": [
                                data.hourly_hits, (n) => $i18n.t("unit.hour", { value: n }), Tools.formatSimpleNumber, $i18n.t("dashboard.value.storage.hits")
                            ],
                            "today_bytes": [
                                data.hourly_bytes, (n) => $i18n.t("unit.hour", { value: n }), Tools.formatBytes, $i18n.t("dashboard.value.storage.bytes")
                            ],
                            "days_hits": [
                                data.daily_hits, (n) => n, Tools.formatSimpleNumber, $i18n.t("dashboard.value.storage.hits")
                            ],
                            "days_bytes": [
                                data.daily_bytes, (n) => n, Tools.formatBytes, $i18n.t("dashboard.value.storage.bytes") 
                            ]
                        })) {
                            var [value, key_unit, value_formatter, i18n] = values;
                            if (!value) continue;
                            if (key.startsWith("today")) {
                                for (let i = 0; i < 24; i++) {
                                    if (value[i]) continue
                                    value[i] = 0
                                }
                                value = Object.fromEntries(
                                    Object.keys(value).sort((a, b) => parseInt(a) - parseInt(b)).map(v => [v, value[v]])
                                )
                            } else {
                                var server_time = $dashboard_locals.info_runtime
                                // object.current_time - object.start_time - object.diff / 1000.0 + (+new Date() - object.resp_timestamp) / 1000.0;
                                var time = server_time.start_time - server_time.diff / 1000.0 + (+new Date() - server_time.resp_timestamp) / 1000.0;
                                const previous = (time - (time % (24 * 3600)) - 86400 * 30);
                                const res = {}
                                for (let i = 0; i < 30; i++) {
                                    var d = Tools.formatDate(new Date((previous + i * 86400) * 1000.0))
                                    if (value[d]) res[d] = value[d]
                                    else res[d] = 0
                                }
                                value = res
                            }
                            var option = {
                                color: [
                                    $style.getThemeValue("echarts-color-0"),
                                ],
                                xAxis: {
                                    data: Object.keys(value).map(
                                        key_unit
                                    ),
                                },
                                yAxis: {
                                    max: Math.max(10, ...Object.values(value)),
                                },
                                series: [{
                                    name: i18n,
                                    data: Object.values(value),
                                    type: 'line',
                                    smooth: true,
                                }]
                            }
                            $dashboard_locals.storage_echarts[key].base.setFormatter(value_formatter)
                            $dashboard_locals.storage_echarts[key].base.setOption(option)
                        }
                    }
                })
                $dashboard_locals.storage_info = createElement("div").append(
                    Tools.createFlexElement().append(
                        Tools.createPanel(({
                            panel
                        }) => {
                            var instance = Tools.createEchartElement(({
                                echart, base
                            }) => {
                                base.style("min-height", "180px")
                                base.style("width", "100%")
                                $dashboard_locals.storage_echarts.today_hits = {
                                    echart, base
                                }
                            })
                            panel.append(
                                createElement("p").classes("title").i18n("dashboard.title.storage.today.hits"),
                                instance
                            )
                        }),
                        Tools.createPanel(({
                            panel
                        }) => {
                            var instance = Tools.createEchartElement(({
                                echart, base
                            }) => {
                                base.style("min-height", "180px")
                                base.style("width", "100%")
                                $dashboard_locals.storage_echarts.today_bytes = {
                                    echart, base
                                }
                            })
                            panel.append(
                                createElement("p").classes("title").i18n("dashboard.title.storage.today.bytes"),
                                instance
                            )
                        })
                    ).child(2).minWidth(900),
                    Tools.createFlexElement().append(
                        Tools.createPanel(({
                            panel
                        }) => {
                            var instance = Tools.createEchartElement(({
                                echart, base
                            }) => {
                                base.style("min-height", "180px")
                                base.style("width", "100%")
                                $dashboard_locals.storage_echarts.days_hits = {
                                    echart, base
                                }
                            })
                            panel.append(
                                createElement("p").classes("title").i18n("dashboard.title.storage.30days.hits"),
                                instance
                            )
                        }),
                        Tools.createPanel(({
                            panel
                        }) => {
                            var instance = Tools.createEchartElement(({
                                echart, base
                            }) => {
                                base.style("min-height", "180px")
                                base.style("width", "100%")
                                $dashboard_locals.storage_echarts.days_bytes = {
                                    echart, base
                                }
                            })
                            panel.append(
                                createElement("p").classes("title").i18n("dashboard.title.storage.30days.bytes"),
                                instance
                            )
                        })
                    ).child(2).minWidth(900)
                )
                var storage_observer_task = null;
                var storage_observer = new ResizeObserver(() => {
                    if (storage_observer_task != null) clearTimeout(storage_observer_task)
                    storage_observer_task = setTimeout(() => {
                        for (const instance of [
                            "days_hits",
                            "days_bytes",
                            "today_hits",
                            "today_bytes"
                        ]) {
                            $dashboard_locals.storage_echarts[instance].echart.resize()
                        }
                    }, 100)
                })
                storage_observer.observe($dashboard_locals.storage_info.origin)

                // push all elements
                basic.push(
                    section.append(
                        info_collection,
                        $dashboard_locals.basic_qps
                    ),
                    createElement("div").classes("pre-switch-container").append(
                        $dashboard_locals.storage_switch.select(0),
                        $dashboard_locals.cluster_switch.select(0)
                    ),
                    $dashboard_locals.storage_info
                )

            })();
            const init_echarts = () => {
                var option = {
                    tooltip: {
                        trigger: 'axis',
                    },
                    stateAnimation: {
                        duration: 300,
                        easing: "cubicOut"
                    },
                    xAxis: {
                        type: "category",
                        show: false,
                    },
                    yAxis: {
                        show: false,
                        type: "value",
                    },
                    grid: {
                        top: 10,
                        bottom: 10,
                        right: 0,
                        left: 0,
                        show: !1,
                        z: 0,
                        containLabel: !1,
                        backgroundColor: "rgba(0,0,0,0)",
                        borderWidth: 1,
                        borderColor: "#ccc"
                    },
                    series: [
                        {
                            type: "bar",
                            barGap: "0",
                            barMinHeight: 4,
                            itemStyle: {
                                borderRadius: [2, 2, 0, 0]
                            },
                            z: 2,
                            backgroundStyle: {
                                color: "rgba(180, 180, 180, 0.2)",
                                borderColor: null,
                                borderWidth: 0,
                                borderType: "solid",
                                borderRadius: 0,
                                shadowBlur: 0,
                                shadowColor: null,
                                shadowOffsetX: 0,
                                shadowOffsetY: 0
                            },
                            select: {
                                itemStyle: {
                                    borderColor: "#212121"
                                }
                            },
                        }
                    ]
                }
                const instances = [
                    $dashboard_locals.basic_qps_echart
                ]
                for (let qps of instances) {
                    qps.echart.setOption(option)
                }

                for (const instance of [
                    "days_hits",
                    "days_bytes",
                    "today_hits",
                    "today_bytes"
                ]) {
                    var option = {
                        /*color: [
                            $style.getThemeValue("echarts-color-0"),
                        ],*/
                        tooltip: {
                            trigger: 'axis'
                        },
                        grid: {
                            left: '3%',
                            right: '4%',
                            bottom: '3%',
                            top: '20%',
                            containLabel: true
                        },
                        xAxis: {
                            type: 'category',
                        },
                        yAxis: {
                            type: 'value',
                            min: 1,
                            max: 10
                        },
                        series: []
                    };
                    $dashboard_locals.storage_echarts[instance].echart.setOption(option)
                }
            }
            // share 
            (() => {
                const instances = [
                    $dashboard_locals.basic_qps_echart
                ]
                $dashboard_locals.qps_data = ref({}, {
                    timeout: 20,
                    handler: (object) => {
                        var resp = object.object.resp;
                        var option = {
                            color: $style.getThemeValue("echarts-color-0"),
                            xAxis: {
                                data: Object.keys(resp)
                            },
                            series: [{ name: 'QPS', data: Object.values(resp) }]
                        }
                        for (let instance of instances) {
                            instance.echart.setOption(option)
                        }
                    }
                })
                $dashboard_locals.qps_task = Tools.runTask(setInterval, async () => {
                    var resp = await $channel.send("qps")
                    $dashboard_locals.qps_data.resp = resp;
                }, 5000)
                window.addEventListener("theme-changed", () => {
                    $dashboard_locals.qps_data.resp = $dashboard_locals.qps_data.resp;
                    $dashboard_locals.statistics_data.refresh = true;
                })
            })();

            const reset_display = () => {
                $dashboard_locals.info_runtime.value = Tools.formatTime(0)
                $dashboard_locals.files_info_30days_bytes.value = Tools.formatBytes(0)
                $dashboard_locals.files_info_30days_hits.value = Tools.formatSimpleNumber(0)
                $dashboard_locals.files_info_today_bytes.value = Tools.formatBytes(0)
                $dashboard_locals.files_info_today_hits.value = Tools.formatSimpleNumber(0)

                $dashboard_locals.system_info_connection.value = Tools.formatSimpleNumber(0)
                $dashboard_locals.system_info_cpu.value = Tools.formatSimpleNumber(0)
                $dashboard_locals.system_info_memory.value = Tools.formatBytes(0)
                
            }

            reset_display()

            $dashboard_locals.pre_switch = createElement("div").classes("pre-switch-container").append(
                new SwitchElement().addButtons("switch.dashboard.basic", "switch.dashboard.advanced").addEventListener("change", (event) => {
                    while ($dashboard_locals.container.firstChild != null) {
                        $dashboard_locals.container.removeChild($dashboard_locals.container.firstChild)
                    }
                    clearEcharts()
                    clearDashboardTask()
                    reset_display()
                    init_echarts()
                    if (event.detail.index == 0) {
                        $dashboard_locals.container.append(
                            ...$dashboard_locals.basic
                        )
                        clearInterval($dashboard_locals.storage_info_task)
                        $dashboard_locals.storage_info_task = Tools.runTask(setInterval, async () => {
                            var hourly = await $channel.send("storage_statistics_hourly")
                            var daily = await $channel.send("storage_statistics_daily")
                            // remove "None"
                            delete hourly["None"]
                            delete daily["None"]
                            var storage = {
        
                            }
                            //console.log(hourly, daily)
                            for (const [key, data] of Object.entries({
                                "hits": {
                                    "daily": Object.entries(daily),
                                    "hourly": Object.entries(hourly)
                                },
                                "bytes": {
                                    "daily": Object.entries(daily),
                                    "hourly": Object.entries(hourly)
                                }
                            })) {
                                for (const [time, values] of Object.entries(data)) {
                                    for (const [storage_id, value] of values) {
                                        if (!storage[storage_id]) storage[storage_id] = {}
                                        var key_time = `${time}_${key}`
                                        if (!storage[storage_id][key_time]) storage[storage_id][key_time] = {}
                                        for (const val of value) {
                                            var v = storage[storage_id][key_time][val._] || 0;
                                            storage[storage_id][key_time][val._] = v + val[key]
                                        }
                                    }
                                }
                            }
                            var total = {
                                hourly_bytes: {},
                                daily_bytes: {},
                                hourly_hits: {},
                                daily_hits: {}
                            }
                            for (const data of Object.values(storage)) {
                                for (const [key, values] of Object.entries(data)) {
                                    for (const [time, value] of Object.entries(values)) {
                                        var v = total[key][time] || 0;
                                        total[key][time] = v + value
                                    }
                                }
                            }
                            $dashboard_locals.statistics_data.total = total;
                            $dashboard_locals.statistics_data.storages = storage;
                        }, 60000)
                        clearInterval($dashboard_locals.basic_task_file_info)
                        $dashboard_locals.basic_task_file_info = Tools.runTask(setInterval, async () => {
                            var hourly = await $channel.send("cluster_statistics_hourly")
                            var daily = await $channel.send("cluster_statistics_daily")
                            var rdata = {}
                            for (const [
                                key, val
                            ] of Object.entries({
                                "hourly_hits": ["hits", hourly],
                                "hourly_bytes": ["bytes", hourly],
                                "daily_hits": ["hits", daily],
                                "daily_bytes": ["bytes", daily],
                            })) {
                                rdata[key] = Object.values(val[1]).map((obj) => obj.reduce((a, b) => a + b[val[0]], 0)).reduce((a, b) => a + b, 0)
                            }
                            // first hits
                            for (const {
                                handler, obj, data
                             } of [
                                {
                                     handler: Tools.formatSimpleNumber,
                                     obj: $dashboard_locals.files_info_today_hits,
                                     data: rdata.hourly_hits
                                },
                                {
                                     handler: Tools.formatSimpleNumber,
                                     obj: $dashboard_locals.files_info_30days_hits,
                                     data: rdata.daily_hits
                                },
                                {
                                     handler: Tools.formatBytes,
                                     obj: $dashboard_locals.files_info_today_bytes,
                                     data: rdata.hourly_bytes
                                },
                                {
                                    handler: Tools.formatBytes,
                                    obj: $dashboard_locals.files_info_30days_bytes,
                                    data: rdata.daily_bytes
                                }
                            ]) {
                                var formatted = handler(data)
                                obj.value = formatted
                            }
                            
                        }, 10000)
                        clearInterval($dashboard_locals.basic_task_system_info)
                        $dashboard_locals.basic_task_system_info = Tools.runTask(setInterval, async () => {
                            var resp = await $channel.send("systeminfo")
                            $dashboard_locals.system_info_connection.value = resp.connection.tcp + resp.connection.udp
                            $dashboard_locals.system_info_memory.value = Tools.formatBytes(resp.memory)
                            $dashboard_locals.system_info_cpu.value = resp.cpu.toFixed(1) + "%"
                            $dashboard_locals.system_info_cpu_load.value = resp.loads.toFixed(1) + "%"
                        }, 1000)
                        /*$channel.send("storage_keys").then((resp) => {
                            $dashboard_locals.storage_switch.addButtons(
                                ...resp.map((val) => "switch.dashboard.storage." + val.data.type)
                            )
                        })*/

                    } else {
                        $dashboard_locals.container.append(
                            ...$dashboard_locals.advanced
                        )
                    }
                    requestAnimationFrame(() => {
                        if ($dashboard_locals.qps_data.resp)
                            $dashboard_locals.qps_data.resp = $dashboard_locals.qps_data.resp;
                        $dashboard_locals.statistics_data.refresh = true;
                    })
                }).select(0)
            )
        }
        $main.append(
            $dashboard_locals.info,
            $dashboard_locals.pre_switch,
            $dashboard_locals.container
        )
    })

    const clearEcharts = (all = false) => {
        const $dashboard_locals = $menu_variables.dashboard;
        if (!$dashboard_locals) return;
        $dashboard_locals.basic_qps_echart.echart.clear()
        for (const instance of Object.values($dashboard_locals.storage_echarts)) {
            instance.echart.clear()
        }
    }

    const clearDashboardTask = (all = false) => {
        const $dashboard_locals = $menu_variables.dashboard;
        if (!$dashboard_locals) return;
        clearInterval($dashboard_locals.basic_task_file_info)
        clearInterval($dashboard_locals.basic_task_system_info)
        clearInterval($dashboard_locals.storage_info_task)
        if (!all) return;
        clearInterval($dashboard_locals.info_runtime_task)
        clearInterval($dashboard_locals.qps_task)
    }

    $router.before_handler(() => {
        while ($main.firstChild != null) {
            $main.removeChild($main.firstChild)
        }
        clearDashboardTask(true)
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
        $menu.style("top", `${header}px`)
        $main.style("margin-top", `${header}px`)
        $main.styleProperty("--height", `${header}px`)
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
