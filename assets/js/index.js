import {
    Configuration,
    Element,
    ElementManager,
    Style,
    I18NManager,
    createElement,
    SVGContainers,
    calcElementHeight,
    calcElementWidth,
    Utils,
    ObjectID,
    ref,
    THEMECHANGEEVENT,
    RouterManager,
} from './common.js'

import './config.js'
import { echarts_china} from './china.js'
import { echarts_world } from './world.js'
import { cn_province, country_code } from './geo_table.js'
const UTC_OFFSET = 3600 * 8
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

        const [
            x, y
        ] = [
            document.body.getBoundingClientRect().width,
            document.body.getBoundingClientRect().height
        ]
        // if is phone, hide menu
        if (x < 1280 || y > x) {
            this.toggle()
        }
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
        $router.beforeHandler(async (event) => {
            if (this._render_task) await new Promise((resolve) => {
                this.route_handler_lock = resolve
            })
            if (event.current_route.length < 2) {
                (() => {
                    const [menu, value] = Object.entries(this.$menus)[0]
                    if (value.children.length != 0) {
                        value.children[0].$dom.click();
                    } else {
                        $router.page("/" + menu)
                    }
                })();
                return;
            }
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
        this.timeout = 20000
        this._event_source_init()
        if (!this.support_websocket) return;
        this._ws_init();
        this._ws_initizalized = false;
        this._ws_callbacks = {};
        this._ws_timeouts = {}
    }
    // event source
    _event_source_init() {
        this._event_source = new EventSource(this.url + "_event");
        this._event_source.onmessage = (e) => {
            const raw_data = JSON.parse(e.data);
            const type = raw_data.event.split("_")[0];
            const event = raw_data.event.slice(type.length + 1);
            const data = raw_data.data;
            window.dispatchEvent(new CustomEvent(`sse_${type}`, {
                detail: {
                    event,
                    data,
                }
            }))
            if (event.length == 0) return;
            window.dispatchEvent(new CustomEvent(`sse_${type}_${event}`, {
                detail: data
            }))
        }
        
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
    }
    _ws_reconnect() {
        if (this._ws_reconnect_task) return;
        this._ws_reconnect_task = setTimeout(() => {
            this._ws_init();
            this._ws_reconnect_task = null;
        }, 5000)
    }

    async _ws_send(event, data, options) {
        if (!this._ws_initizalized) return this._http_send(event, data);
        return new Promise(async (resolve, reject) => {
            var echo_id = (await ObjectID.create()).toString();
            this._ws_callbacks[echo_id] = { resolve, reject }
            this._ws.send(JSON.stringify({
                event,
                data,
                echo_id
            }))
            if (options.timeout) {
                this._ws_timeouts[echo_id] = setTimeout(() => {
                    delete this._ws_callbacks[echo_id];
                    reject("timeout")
                }, options.timeout)   
            }
        })
    }

    async _http_send(event, data, options) {
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
            if (options?.timeout) {
                var timer = setTimeout(() => {
                    xhr.abort();
                    reject("timeout")
                }, options.timeout)
            }
        })
    }

    async send(event, data, options = {
        "timeout": this.timeout
    }) {
        var noptions = {
            ...{
                "timeout": this.timeout
            },
            ...options
        }
        if (this.support_websocket) return this._ws_send(event, data, noptions);
        return this._http_send(event, data, noptions);
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
                white-space: nowrap;
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
            if (this.index == null) return;
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
    removeButtons(...button) {
        // remove of button value
        for (let button_value of button) {
            this._buttons = this._buttons.filter(e => e != button_value);
        }
        if (this._render_task) return this;
        this._render_task = requestAnimationFrame(() => {
            this._render();
        })
        return this;
    }
    getInstanceButtons() {
        return this.$buttons;
    }
    getButtons() {
        return this._buttons;
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
            if (this.index == button_index) {
                this._render_bar()
            }
        }
        this.$main.append(...this.$buttons)
        if (this._render_next_index != null) {
            const next_index = this._render_next_index;
            this._render_next_index = null;
            requestAnimationFrame(() => {
                this.select(next_index);
            })
        }
    }
    _render_bar() {
        requestAnimationFrame(() => {
            var index = this.index;
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
        })
    }
    select(index) {
        if (this._render_task || this.$buttons.length == 0) {
            this._render_next_index = index;
            return this;
        };
        var oldindex = this.index;
        this.index = index;
        this._render_bar()
        if (oldindex == this.index) return this;
        this.origin.dispatchEvent(new CustomEvent("change", {
            detail: this.current
        }))
        return this;
    }

    get current() {
        return {
            index: this.index,
            instanceButton: this.$buttons[this.index],
            button: this._buttons[this.index]
        }
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
            handler = (child) => this._render_calc_child_value(this.children.length, this.children.indexOf(child), container_width)
            heightHandler = (child) => calcElementHeight(child)
        }
        for (const child of this.children) {
            var res = handler(child);
            child.style("width", `${res}px`)
            if (this.$autoheight) {
                requestAnimationFrame(() => {
                    child.style("height", `${heightHandler(child)}px`)
                })
            }
            child.origin.getBoundingClientRect()
        }
    }
    _render_calc_child_value(total_child, index, container_value) {
        const child = this.$child;
        if (child.length == 1) {
            var val = child[0];
            // if val is number
            if (typeof val === "number") {
                return container_value / val;
            }
            if (val.endsWith("%")) {
                return parseFloat(val.slice(0, -1)) / 100.0 * container_value / total_child;
            }
            return 0;
        }
        // first check if all child is number, or all child is percent
        const is_number = child.every(e => typeof e === "number");
        const is_percent = child.every(e => typeof e === "string" && e.endsWith("%"));
        if (is_number) {
            return child[index >= child.length ? child.length - 1 : index] / total_child * container_value;
        }
        if (is_percent) {
            var total = child.reduce((a, b) => a + parseFloat(b.slice(0, -1)), 0);
            return parseFloat(child[index >= child.length ? child.length - 1 : index].slice(0, -1)) / total * container_value;
        }
        console.error(child, " is not a valid value value");
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
        this.formatters = [
            this._format_number_unit,
        ]
        this.type = EchartType.DATA
        this.$current_options = []
        //this._defaultInit()
        this.instance.showLoading()
    }
    _defaultInit() {
        this.setOption({
            stateAnimation: {
                duration: 300,
                easing: "cubicOut"
            },
            tooltip: {
                trigger: 'axis',
                formatter: (params) => this._e_templates(params)
            },
            backgroundColor: 'rgba(0, 0, 0, 0)'
        })
    }
    setFormatter(formatter, index = 0) {
        if (index >= this.formatters.length) {
            this.formatters.push(formatter)
        }
        this.formatters[index] = formatter
        return this
    }
    _baseSetOption(option) {
        this.$current_options.push(option)
        this.instance.setOption(option)
    }
    setOption(option) {
        this._baseSetOption(option)
        var options = {}
        if (!('tooltip' in option && 'formatter' in option['tooltip'])) {
            options.tooltip = {
                ...option['tooltip'],
                formatter: (params) => this._e_templates(params)
            }
        }
        if ('yAxis' in option) {
            var o = {}
            if (!('axisLabel' in option['yAxis'])) o.axisLabel = {
                formatter: (params) => this.formatters[0](params)
            }
            if (!('splitLine' in option['yAxis'])) o.splitLine = {
                color: $style.getThemeValue("dark-color"),
                type: "dashed"
            }
            options.yAxis = {
                ...option['yAxis'],
                ...o
            }
        }
        if ('xAxis' in option) {
            var func = (o) => {
                return {
                    ...o,
                    splitLine: {
                        color: $style.getThemeValue("dark-color"),
                        type: "dashed"
                    }
                }
            }
            var to = []
            if (!Array.isArray(option['xAxis'])) {
                to.push(option['xAxis'])
            } else {
                to = option['xAxis']
            }
            for (var i = 0; i < to.length; i++) {
                to[i] = func(to[i])
            }
            options.xAxis = to.length == 1 ? to[0] : to
        }
        this._baseSetOption(options)
        this.instance.hideLoading()
        return this
    }
    setType(type) {
        this.type = type
        return this
    }
    clear() {
        this.instance.showLoading()
        this.instance.clear()
        this.$current_options = []
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
        const data_label = this.type == EchartType.LABEL
        const templates = `<div style="margin: 0px 0 0;line-height:1"><div style="margin: 0px 0 0;line-height:1">` + (data_label ? '' : `<span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:{color}"></span>`) + `<span style="font-size:14px;color:#666;font-weight:400;margin-left:2px">{name}</span><span style="float:right;margin-left:20px;font-size:14px;color:#666;font-weight:900">{value}</span><div style="clear:both"></div></div><div style="clear:both"></div></div>`
        var template = ''
        for (const data of (Array.isArray(params) ? params : [params])) {
            let value_formatter = this.formatters[data.seriesIndex] || this.formatters[0]
            let value = isNaN(data.value) ? 0 : data.value
            template += templates.replace("{color}", data.color).replace("{name}", `${data.seriesName}${data_label ? `(${data.data.label})` : ""}`).replace("{value}", value_formatter ? value_formatter(value) : value)
        }
        return `<div style="margin: 0px 0 0;line-height:1"><div style="margin: 0px 0 0;line-height:1">` + (data_label ? `` : `<div style="font-size:14px;color:#666;font-weight:400;line-height:1">${(Array.isArray(params) ? params[0] : params).name}</div>`) + `<div style="margin: ${data_label ? 0 : 10}px 0 0;line-height:1">${template}</div><div style="clear:both"></div></div><div style="clear:both"></div></div>`
    }
    getOption() {
        return this.instance.getOption()
    }
    showLoading() {
        this.instance.showLoading()
        return this
    }
    hideLoading() {
        this.instance.hideLoading()
        return this
    }
}
const $configuration = new Configuration();
const $ElementManager = new ElementManager();
const $style = new Style($configuration);
const $i18n = new I18NManager();
const $router = new RouterManager("/pages");
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
    "dashboard.title.qps": "实时 QPS",
    "switch.dashboard.cluster.:all:": "所有节点",
    "dashboard.title.storage.today": "今日请求存储",
    "dashboard.title.storage.30days": "30 天请求存储",
    "dashboard.title.cluster.today": "今日请求节点",
    "dashboard.title.cluster.30days": "30 天请求节点",
    "dashboard.value.unit.bytes": "请求量",
    "dashboard.value.unit.hits": "请求数",
    "dashboard.switch.storage.local": "本地存储 [%path%]",
    "dashboard.switch.storage.alist": "Alist [%url%%path%]",
    "dashboard.switch.storage.webdav": "WebDAV [%url%%path%]",
    "dashboard.switch.storage.undefined": "未知存储",
    "dashboard.switch.storage._interface": "奇怪的存储",
    "dashboard.value.storage.total.today": "共请求 %hits% | 共请求流量 %bytes%",
    "dashboard.value.cluster.total.today": "共请求 %hits% | 共请求流量 %bytes%",
    "dashboard.value.storage.total.30days": "共请求 %hits% | 共请求流量 %bytes%",
    "dashboard.value.cluster.total.30days": "共请求 %hits% | 共请求流量 %bytes%",
    "dashboard.value.status.clusters": "节点正常运行（%online%/%total%）",
    "dashboard.value.status.cluster.status.checking_files": "检查文件中",
    "dashboard.value.status.clusters.enabling": "启用节点中（%online%/%total%）",
    "dashboard.value.status.cluster.status.listing_files": "列出存储文件中",
    "dashboard.value.status.cluster.status.get_certificates": "正在获取证书中",
    "dashboard.value.status.cluster.fetch_filelist": "获取文件列表中",
    "dashboard.value.status.default": "加载中……",
    "dashboard.value.status.storage.check_available": "检查可用存储",
    "dashboard.value.status.cluster.status.sync": "同步文件中",
    "dashboard.title.req_map": "请求访问分布",
    "req_map.world": "世界",
    "req_map.china": "中国",
    "dashboard.title.ip_access": "IP 访问分布",
    "dashboard.access": "访问数",
    "advanced.time.switch.day.1": "24 小时",
    "advanced.time.switch.day.7": "7 天",
    "advanced.time.switch.day.30": "30 天",

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
    "panel-box-shadow": "rgba(145, 158, 171, 0.2) 0px 4px 10px",
    "panel-color": "rgb(255, 255, 255)",
    "title-color": "rgba(0, 0, 0, 0.5)",
    "value-color": "rgba(0, 0, 0, 0.7)",
    "echarts-color-0": "#0FC6C2",//"#246de6",
    "echarts-color-1": "#6199FE",
    "echarts-color-2": "#FFD268",
    "echarts-color-3": "#FF5576",
    "echarts-color-4": "#89DFE2",
    "echarts-main-line-color": "#0FC6C2",
    "echarts-main-color": "#0FC6C2",
    "echarts-dark-color": "#4260f0",
    "echarts-none-color": "#eefbfb",
    "echarts-area-color": "#F7F8FA",
    "echarts-border-color": "#CCC",
    "echarts-emphasis-color": "#ADD8E6",
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
    "background": "rgb(24, 24, 24)",
    "footer-background": "#202020",
    "background-hover": "#202020",
    "main-dark-color": "rgb(235, 187, 151)",
    "main-shadow-0-2-color": "rgba(244, 209, 180, 0.2)",
    "main-shadow-0-1-color": "rgba(244, 209, 180, 0.1)",
    "panel-box-shadow": "none",
    "panel-color": "rgb(35, 35, 35)",
    "title-color": "rgba(255, 255, 255, 0.5)",
    "value-color": "rgb(255, 255, 255)",
    "echarts-color-0": "#F4D1B4",
    "echarts-color-1": "#FFA552", 
    "echarts-color-2": "#F16575", 
    "echarts-color-3": "#65B8FF", 
    "echarts-color-4": "#FF8859",
    "echarts-main-line-color": "#0FC6C2",
    "echarts-main-color": "#FF8859",
    "echarts-dark-color": "#4260f0",
    "echarts-none-color": "#F4D1B4",
    "echarts-area-color": "#494949",
    "echarts-border-color": "#CCC",
    "echarts-emphasis-color": "#ADD8E6",
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
    "h1,h2,h3,h4,h5,h6,p": "margin:0;color:inherit;font-family:inherit",
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
        "overflow": "auto",
        "display": "flex",
        "flex-wrap": "nowrap",
        "flex-direction": "row",
        "justify-content": "space-between"
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
    `,
    ".label-text .flex-between": {
        "flex-direction": "row",
        "justify-content": "space-between"
    },
    ".info-progressbar": {
        "display": "flex",
        "margin-top": "8px",
        "border-top": "1px solid var(--title-color)",
        "padding-top": "8px"
    },
    ".info-progressbar.hidden": {
        "display": "none"
    },
    ".info-progressbar .container-bar": {
        "margin-left": "8px",
        "margin-right": "8px",
        "display": "flex",
        "flex-grow": 1,
        "align-items": "center",
    },
    ".info-progressbar .container-bar .bar": {
        "padding": "2px",
        "margin-left": "8px",
        "height": "4px",
        "background": "var(--main-color)",
        "border-radius": "8px",
        "width": "100%",
        "transition": "width 0.5s ease-in-out"
    },
    ".map-container": {
        "min-height": "455px"
    },
    ".echart": {
        "margin-top": "8px"
    },
    ".qps-bar": {
        "font-family": "Mono",
        "display": "flex",
        "padding-left": "8px",
        "padding-right": "8px",
        "-webkit-box-align": "center",
        "align-items": "center",
        "background-color": "rgba(0, 0, 0, 0.05)",
        "border-radius": "4px",
        "margin-left": "16px",
    },
    "@font-face": {
        "font-family": "Mono",
        "src": "url('/assets/fonts/Mono.min.ttf')",
        "font-weight": "normal",
        "font-style": "normal"
    }
})
class Tools {
    static _NUMBER_UNITS = {
        "": 1,
        "K": 1e3,
        "M": 1e3,
        "B": 1e3,
        "T": 1e3,
        "P": 1e3,
        "E": 1e3,
        "Z": 1e3,
        "Y": 1e3,
    }
    static formatTime(seconds) {
        if (seconds < 0 || seconds == null) return $i18n.t("format.count_time.days", {
            day: "--",
            hour: "--",
            minute: "--",
            second: "--",
        })
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
    static formatCountTime(seconds) {
        if (seconds < 0 || seconds == null) return "--:--"
        var s = Math.floor(seconds % 60)
        var m = Math.floor(seconds / 60 % 60)
        var h = Math.floor(seconds / 3600 % 24)
        if (h > 0) return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
        return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
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
        aria_label_value: () => { },
        aria_label_title: () => { },
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
                var title = ref({}, {
                    handler: (args) => {
                        label[key].aria_label(args.object.value)
                    }
                })
                var obj = ref({}, {
                    handler: (args) => {
                        label[key].t18n(args.object)
                    }
                })
                var handlers = [
                    [params[key + "_variable"], obj],
                    [params["aria_label_" + key], title],
                ]
                for (let [handler, o] of handlers) {
                    if (!handler) continue;
                    try {
                        handler(o)
                    } catch (e) {
                        console.error(e)
                    }
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
    static createElementWithI18n(
        tag,
        options = {
            key: "",
            callback: () => { }
        }
    ) {
        var element = createElement(tag)
        var obj = ref({}, {
            handler: (args) => {
                element.t18n(key, args.object)
            }
        })
        options.callback(obj)
        return element
    }
    static formatSimpleNumber(number) {
        // convert number to belike: 100,000, if 100000.0, we are 100,000.0
        return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ", ")
    }
    static formatUnitNumber(number) {
        var i = 0
        for (const [u, un] of Object.entries(Tools._NUMBER_UNITS).slice(1)) {
            if (number / un < 1) {
                break
            }
            number /= un
            i += 1
        }
        let unit = Object.keys(Tools._NUMBER_UNITS)[i]
        return `${number.toFixed(unit.length != 0 ? (number % 1 == 0 ? 0 : 1) : 2)}${unit}`
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
    static formatDateHourMinute(d) {
        return `${d.getFullYear().toString().padStart(4, "0")}-${(d.getMonth() + 1).toString().padStart(2, "0")}-${d.getDate().toString().padStart(2, "0")} ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`
    }
}
class UserAuth {
    constructor() {
        $router.on("/auth", () => {
            // ...
        })
    }
    get triggerGUI() {
        return SVGContainers.user.addEventListener("click", () => {
            // ...
        })
    }
}
class DynmaticQPS extends Element {
    constructor() {
        super("div").classes("dynmatic-qps")
        $style.addAll({
            ".dynmatic-qps": {
                "width": "14px",
                "height": "14px",
                "margin-right": "8px"
            },
            ".dynmatic-qps .container": {
                "width": "100%",
                "height": "100%",
                "display": "grid",
                "grid-template-columns": "repeat(3, 1fr)",
                "gap": "15%",
                "align-items": "end"
            },
            ".dynmatic-qps .child": {
                "border-radius": "2px 2px 0px 0px",
                "background-color": "var(--main-color)",
                "transition": "height 0.3s ease-in-out"
            }
        })
        this.$container = createElement("div").classes("container")
        for (let i = 0; i < 3; i++) {
            this.$container.append(createElement("div").classes("child"))
        }
        this.append(this.$container)
        this.smooth = 0.01
        this.datas = [
            0.3, 0.7, 0.4
        ]
        this.states = Array.from(this.datas).map(e => e)
        this.update()
    }
    update(mode = false) {
        for (let idx in this.$container.children) {
            let child = this.$container.children[idx]
            let value = this.datas[idx]
            if (mode) {
                value += value > 0.5 ? -0.4 : 0.4
            }
            child.style("height", `${value * 100}%`)
        }
        setTimeout(() => {
            this.update(!mode)
        }, 750);
    }
}
const $userAuth = new UserAuth();

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
            $theme_change,
            $userAuth.triggerGUI,
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
                $dashboard_locals.info_progressbar_bar = {
                    rate: createElement("p").classes("text"),
                    bar: createElement("div").classes("bar"),
                    desc: createElement("p").classes("text"),
                    postfix: createElement("p").classes("text"),
                }
                $dashboard_locals.info_progressbar = createElement("div").classes("info-progressbar", "hidden").append(
                    $dashboard_locals.info_progressbar_bar.desc,
                    createElement("div").classes("container-bar").append(
                        $dashboard_locals.info_progressbar_bar.rate,
                        $dashboard_locals.info_progressbar_bar.bar,
                    ),
                    $dashboard_locals.info_progressbar_bar.postfix,
                )
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
                                        "dashboard.value.status": "%value%"
                                    }
                                }
                            }),
                        ).child(2).minWidth(680),
                        $dashboard_locals.info_progressbar
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
                const status_handlers = {
                    "clusters_clusters": (data) => {
                        return {
                            "total": data.params.total,
                            "online": data.count 
                        }
                    },
                    "clusters_clusters.enabling": (data) => {
                        return {
                            "total": data.params.total,
                            "online": data.count,
                            "enabling": data.params.enabling
                        }
                    },
                }
                window.addEventListener("sse_status", event => {
                    const obj = $dashboard_locals.status
                    // 先 sort cluster 在前面，然后再storage
                    const clusters = [];
                    const storages = [];
                    for (const item of event.detail.data) {
                        if (item.name.startsWith("cluster")) clusters.push(item)
                        else storages.push(item)
                    }
                    clusters.sort((a, b) => a.name.localeCompare(b.name))
                    storages.sort((a, b) => a.name.localeCompare(b.name))
                    var params = {}
                    var key = "default";
                    if (clusters.length != 0) {
                        const cluster = clusters[0];
                        key = cluster.name;
                        params = (status_handlers["clusters_" + key] || (() => { }))(cluster) || {};
                    } else if (storages.length != 0) {
                        const storage = storages[0];
                        key = storage.name;
                        params = (status_handlers["storages_" + key] || (() => { }))(storage) || {};
                    }
                    obj.value = $i18n.t(`dashboard.value.status.${key}`, params)
                    if (obj.value == `dashboard.value.status.${key}`) console.log(`dashboard.value.status.${key}`)
                })
                window.addEventListener("sse_progress", event => {
                    const resp = event.detail.data;
                    const isEmpty = resp.length == 0
                    if (isEmpty) {
                        $dashboard_locals.info_progressbar.classes("hidden")
                        $dashboard_locals.info_progressbar_bar.bar.style("width", "0%")
                        return
                    }
                    const data = resp[0];
                    const rate = ((data.total == 0 || data.total < data.current ? 1 : data.current / data.total) * 100.0);
                    $dashboard_locals.info_progressbar_bar.desc.text(data.desc)
                    $dashboard_locals.info_progressbar_bar.rate.text(rate.toFixed(2) + "%")
                    $dashboard_locals.info_progressbar_bar.bar.style("width", rate + "%")

                    // calc elapsed time
                    if (rate < 100) {
                        var speed = (data.speed.slice(data.speed.length - 1) || [0])[0];
                        var e = speed == 0 ? null : (data.total - data.current) / speed;
                        var d = Tools.formatCountTime(e);
                        var running = Tools.formatCountTime(data.current_time - data.start_time);
                        var postfix = data.postfix == null ? "" : ", " + data.postfix;
                        var current = data.current;
                        var total = data.total;
                        if (data.unit == "b") {
                            speed = Tools.formatBytes(speed)
                            current = Tools.formatBytes(current)
                            total = Tools.formatBytes(total)
                            data.unit = ""
                        } else {
                            speed = Tools.formatUnitNumber(speed)
                            current = Tools.formatUnitNumber(current)
                            total = Tools.formatUnitNumber(total)
                        }
                        $dashboard_locals.info_progressbar_bar.postfix.text(`${data.current}/${data.total} [${running}<${d}, ${speed.toFixed(2)}${data.unit}/s${postfix}]`)
                    }

                    $dashboard_locals.info_progressbar.removeClasses("hidden")
                    

                })
            })();

            const create_qps = (
                type = "basic",
                parentElement = null,
                leftElement = null
            ) => {
                return Tools.createPanel(({ pre, panel }) => {
                    var instance = Tools.createEchartElement(({
                        echart, base
                    }) => {
                        base.classes("echart").style("min-height", "172px")
                        $dashboard_locals[`${type}_qps_echart`] = {
                            echart, base
                        };
                    })
                    var current_qps = createElement("p")
                    var counter = ref({}, {
                        handler: (obj) => {
                            current_qps.text(obj.object.value)
                        }
                    })
                    panel.classes("label-text").append(
                        createElement("div").classes("title").append(
                            createElement("p").i18n("dashboard.title.qps"),
                            createElement("div").classes("qps-bar").append(
                                new DynmaticQPS(),
                                current_qps
                            )
                        ),
                        instance
                    )
                    $dashboard_locals[`${type}_qps_counter`] = counter
                    counter.value = 0
                    var observer = new ResizeObserver(() => {
                        var width = calcElementWidth(parentElement)
                        if (width < 1280) {
                            pre.style("height", `auto`)
                        } else {
                            pre.style("height", `${calcElementHeight(leftElement) / (type == "basic" ? 1 : 2)}px`)
                            panel.style("height", "100%")
                        }
                        $dashboard_locals[`${type}_qps_echart`].echart.resize()
                    })
                    observer.observe(leftElement.origin)
                })
            }
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
                                aria_label_value: (obj) => {
                                    $dashboard_locals.files_info_today_hits_label = obj;
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
                                aria_label_value: (obj) => {
                                    $dashboard_locals.files_info_30days_hits_label = obj;
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
                $dashboard_locals.basic_qps = create_qps("basic", section, info_collection)

                // storage

                $dashboard_locals.storage_switch = new SwitchElement().addButtons("switch.dashboard.storage.:all:").addEventListener("change", (event) => {
                    $dashboard_locals.storage_data.refresh = true
                })
                $dashboard_locals.cluster_switch = new SwitchElement().addButtons("switch.dashboard.cluster.:all:").addEventListener("change", (event) => { 
                    $dashboard_locals.storage_data.refresh = true
                })
                $dashboard_locals.storage_echarts = {}
                $dashboard_locals.statistics_key_data = {}
                $dashboard_locals.statistics_keys = ref({
                    clusters: [],
                    storages: []
                }, {
                    timeout: 50,
                    async handler(obj) {
                        const mappings = {
                            "cluster": (n) => {
                                return obj.object.clusters_name[n] || n
                            },
                            "storage": (n) => {
                                var data = obj.object.storages_name[n] || {}
                                if (data.name === undefined || data.name == null || data.name == n) return $i18n.t(`dashboard.switch.storage.${data.type}`, data)
                                return data.name
                            }
                        }
                        for (
                            const key of [
                                "cluster",
                                "storage"
                            ]
                        ) {
                            var section = $dashboard_locals[`${key}_switch`]
                            var obj_key = `${key}s`
                            var value = mappings[key]
                            if (Utils.equals(obj.object[obj_key], obj.before[obj_key])) continue
                            section.removeButtons(...section.getButtons().slice(1))
                            section.addButtons(...obj.object[obj_key].map(e => value(e)))
                        }
                    }
                })
                const get_keys = (data) => {
                    if (!data) return []
                    var res = [];
                    for (var key of Object.keys(data)) {
                        if (key == ":all:") continue
                        res.push(key)
                    }
                    return res
                }
                $dashboard_locals.storage_data = ref({}, {
                    timeout: 50,
                    handler(obj) {
                        // show load
                        for (const instance of Object.values($dashboard_locals.storage_echarts)) {
                            instance.base.showLoading();
                        }


                        $dashboard_locals.statistics_keys.clusters = get_keys(obj.object.cluster)
                        $dashboard_locals.statistics_keys.storages = get_keys(obj.object.storage)

                        $dashboard_locals.statistics_keys.clusters_name = $dashboard_locals.statistics_key_data.clusters
                        $dashboard_locals.statistics_keys.storages_name = $dashboard_locals.statistics_key_data.storages

                        const storage_key = $dashboard_locals.storage_switch.current.index == 0 ? ":all:" : $dashboard_locals.statistics_keys.storages[$dashboard_locals.storage_switch.current.index - 1]
                        const cluster_key = $dashboard_locals.cluster_switch.current.index == 0 ? ":all:" : $dashboard_locals.statistics_keys.clusters[$dashboard_locals.cluster_switch.current.index - 1]
                        if (!obj.object.cluster || !obj.object.storage) return
                        const data = {
                            cluster: obj.object.cluster[cluster_key],
                            storage: obj.object.storage[storage_key]
                        }
                        const mappings = {
                            "hourly": "today",
                            "daily": "30days"
                        }
                        const mappings_unit = {
                            "hourly": (n) => $i18n.t("unit.hour", { value: n }),
                            "daily": (n) => n,//$i18n.t("unit.day", { value: n })
                        }
                        const mappings_formatter = {
                            "hits": Tools.formatSimpleNumber,
                            "bytes": Tools.formatBytes
                        }
                        for (const [key, value] of Object.entries(data)) {
                            value.hourly = value.hourly || {}
                            for (const [time, response] of Object.entries(value)) {
                                const instance = $dashboard_locals.storage_echarts[`${key}_${mappings[time]}`]
                                var resp = response || {}
                                if (time == "hourly") {
                                    for (let i = 0; i < 24; i++) {
                                        if (resp[i]) continue
                                        resp[i] = null
                                    }
                                    resp = Object.fromEntries(
                                        Object.keys(resp).sort((a, b) => parseInt(a) - parseInt(b)).map(v => [v, resp[v]])
                                    )
                                } else {
                                    var server_time = $dashboard_locals.info_runtime
                                    //    return int((t - ((t + UTC) % 86400) - 86400 * day) / 3600)
                                    var datetime = server_time.current_time - server_time.diff / 1000.0 + (+new Date() - server_time.resp_timestamp) / 1000.0;
                                    const previous = (datetime - ((datetime + UTC_OFFSET) % 86400) - 86400 * 29);
                                    const res = {}
                                    for (let i = 0; i < 30; i++) {
                                        var d = Tools.formatDate(new Date((previous + i * 86400) * 1000.0))
                                        if (resp[d]) res[d] = resp[d]
                                        else res[d] = null
                                    }
                                    resp = res
                                }
                                var option = {
                                    //darkMode: $style.isDark,
                                    color: [
                                        $style.getThemeValue("echarts-color-0"),
                                        $style.getThemeValue("echarts-color-1"),
                                    ],
                                    xAxis: {
                                        data: Object.keys(resp).map(
                                            mappings_unit[time]
                                        )
                                    },
                                    yAxis: [
                                        {
                                            name: $i18n.t("dashboard.value.unit.bytes"),
                                            type: 'value',
                                            //max: Math.max(10, ...Object.values(resp).map(v => v?.bytes)),
                                        },
                                        {
                                            position: "right",
                                            name: $i18n.t("dashboard.value.unit.hits"),
                                            type: 'value',
                                            //max: Math.max(10, ...Object.values(resp).map(v => v?.hits)),
                                        },
                                    ],
                                    series: [{
                                        name: $i18n.t("dashboard.value.unit.bytes"),
                                        data: Object.values(resp).map(v => v?.bytes),
                                        type: 'line',
                                        smooth: true,
                                        areaStyle: {}
                                    }, {
                                        name: $i18n.t("dashboard.value.unit.hits"),
                                        data: Object.values(resp).map(v => v?.hits),
                                        type: 'line',
                                        smooth: true,
                                        areaStyle: {},
                                        yAxisIndex: 1
                                    }]
                                }
                                instance.base.setFormatter(mappings_formatter.bytes, 0)
                                instance.base.setFormatter(mappings_formatter.hits, 1)
                                instance.base.setOption(option)

                                instance.total_params.hits = Tools.formatSimpleNumber(Object.values(resp).map(v => v?.hits || 0).reduce((a, b) => a + b, 0))
                                instance.total_params.bytes = Tools.formatBytes(Object.values(resp).map(v => v?.bytes || 0).reduce((a, b) => a + b, 0))
                            }
                        }
                    }
                })
                for (const locals_info_key of [
                    "storage", 
                    "cluster"
                ]) {
                    const info = Tools.createFlexElement()
                    for (const time of [
                        "today",
                        "30days"
                    ]) {
                        info.append(
                            Tools.createPanel(({
                                panel
                            }) => {
                                var instance = Tools.createEchartElement(({
                                    echart, base
                                }) => {
                                    base.style("min-height", "180px")
                                    base.style("width", "100%")
                                    $dashboard_locals.storage_echarts[`${locals_info_key}_${time}`] = {
                                        echart, base
                                    }
                                })
                                var current = createElement("p").i18n(`dashboard.value.${locals_info_key}.total.${time}`)
                                var params = ref({
                                    hits: 0,
                                    bytes: "0iB"
                                }, {
                                    handler(obj) {
                                        current.t18n(obj.object)
                                    },
                                    trigger: true
                                })
                                panel.classes("label-text").append(
                                    createElement("p").classes("title", "flex-between").append(
                                        createElement("p").i18n(`dashboard.title.${locals_info_key}.${time}`),
                                        current
                                    ),
                                    instance
                                )
                                $dashboard_locals.storage_echarts[`${locals_info_key}_${time}`].total_params = params
                            })
                        )
                    }
                    $dashboard_locals[`${locals_info_key}s_info`] = info.child(2).minWidth(1280)
                }

                var statistics = createElement("div").append(
                    createElement("div").classes("pre-switch-container").append(
                        $dashboard_locals.storage_switch.select(0),
                    ),
                    $dashboard_locals.storages_info,
                    createElement("div").classes("pre-switch-container").append(
                        $dashboard_locals.cluster_switch.select(0),
                    ),
                    $dashboard_locals.clusters_info
                )
                const echarts_resize = () => {
                    requestAnimationFrame(() => {
                        for (var instance of Object.values($dashboard_locals.storage_echarts)) {
                            instance.echart.resize();
                        }
                    })
                }
                var observer = new ResizeObserver(echarts_resize)

                observer.observe(statistics.origin);

                // push all elements
                basic.push(
                    section.append(
                        info_collection,
                        $dashboard_locals.basic_qps
                    ),
                    statistics
                )
            })();

            // pro
            (() => {
                const advanced = $dashboard_locals.advanced;
                var waitTaskResponse = {
                    ip_access: false
                }
                var nextTaskResponse = {
                    ip_access: false,
                    geo: false
                }
                var render_ip_access = async () => {
                    if (waitTaskResponse.ip_access) {
                        nextTaskResponse.ip_access = true;
                        return;
                    }
                    waitTaskResponse.ip_access = true;
                    var type = $dashboard_locals.advanced_time_switch.current.button
                    var day = +type.slice(type.lastIndexOf(".") + 1)
                    var ip_access = await $channel.send("response_ip_access", day)
                    var resp = {}
                    var server_time = $dashboard_locals.info_runtime
                    var datetime = (server_time.current_time - server_time.diff / 1000.0 + (+new Date() - server_time.resp_timestamp) / 1000.0);
                    var previous;
                    if (day == 30) {
                        previous = (datetime - ((datetime + UTC_OFFSET) % 86400) - 86400 * day);
                        for (var i = 0; i <= day; i++) {
                            let key = Tools.formatDate(new Date((previous + 86400 * i) * 1000.0))
                            resp[key] = ip_access[key] || 0
                        }
                    } else {
                        previous = (datetime - ((datetime + UTC_OFFSET) % 3600) - 3600 * (day * 24));
                        for (var i = 0; i <= day * 24; i++) {
                            let key = Tools.formatDateHourMinute(new Date((previous + i * 3600) * 1000.0))
                            resp[Tools.formatDateHourMinute(new Date((previous + i * 3600) * 1000.0))] = ip_access[key] || 0
                        }
                    }
                    $dashboard_locals.advanced_ip_access_echarts.base.setOption({
                        xAxis: {
                            data: Object.keys(resp),
                        },
                        series: [{
                            data: Object.values(resp),
                        }]
                    })
                    waitTaskResponse.ip_access = false;
                    if (nextTaskResponse.ip_access) {
                        nextTaskResponse.ip_access = false;
                        await render_ip_access()
                    }
                }
                var render_geo = async () => {
                    if (waitTaskResponse.geo) {
                        nextTaskResponse.geo = true;
                        return;
                    }
                    waitTaskResponse.geo = true;
                    var type = $dashboard_locals.advanced_time_switch.current.button
                    var day = +type.slice(type.lastIndexOf(".") + 1)
                    var cn = $dashboard_locals.advanced_geo_switch.current.button.endsWith("china");
                    var geo_data = await $channel.send("response_geo", {
                        day,
                        cn
                    }, {
                        timeout: 60000
                    })
                    $dashboard_locals.advanced_req_map_echarts_data.data = {
                        cn,
                        data: geo_data
                    }
                    waitTaskResponse.geo = false;
                    if (nextTaskResponse.geo) {
                        nextTaskResponse.geo = false;
                        await render_geo()
                    }
                }
                $dashboard_locals.advanced_task_trigger = ref({}, {
                    timeout: 50,
                    handler: async () => {
                        await Promise.all(
                            [
                                render_ip_access(),
                                render_geo()
                            ]
                        )
                    }
                })
                $dashboard_locals.advanced_time_switch = (new SwitchElement()).addButtons(
                    "advanced.time.switch.day.1",
                    "advanced.time.switch.day.7",
                    "advanced.time.switch.day.30",
                ).select(0).addEventListener("change", () => {
                    $dashboard_locals.advanced_task_trigger.value = ""
                })

                const req_section = Tools.createFlexElement().child('75%', '25%').minWidth(1280)//.autoHeight(true);
                const req_map = Tools.createPanel(({
                    panel
                }) => {
                    var map_container = Tools.createEchartElement((e) => {
                        $dashboard_locals.advanced_req_map_echarts = e
                        $dashboard_locals.advanced_req_map_echarts_data = ref({}, {
                            handler: (obj) => {
                                if (obj.key == "refresh") {
                                    $dashboard_locals.advanced_req_map_echarts.base.setOption({
                                        visualMap: {
                                            inRange: {
                                                color: [$style.getThemeValue("echarts-none-color"), $style.getThemeValue("echarts-main-color")]
                                            },
                                            textStyle: {
                                                color: $style.getThemeValue("echarts-main-color")
                                            },
                                        },
                                        series: {
                                            itemStyle: {
                                                normal: {
                                                    areaColor: $style.getThemeValue("echarts-area-color"),//'#F7F8FA',
                                                    borderColor: $style.getThemeValue("echarts-border-color")//'#CCC'
                                                },
                                                emphasis: {
                                                    areaColor: $style.getThemeValue("echarts-emphasis-color"),//'#ADD8E6',
                                                    borderColor: $style.getThemeValue("dark-color")//'#ffffff'
                                                }
                                            },
                                            name: $i18n.t("dashboard.access")
                                        }
                                    })
                                    return;
                                }
                                var {
                                    cn,
                                    data
                                } = obj.object.data;
                                var resp_data = {};
                                var table = cn ? cn_province : country_code
                                var max = 100;
                                var unknown_codes = [];
                                for (let [code, count] of Object.entries(data)) {
                                    if (table[code]) {
                                        resp_data[table[code]] = count
                                    } else {
                                        resp_data[code] = count
                                        unknown_codes.push(code)
                                    }
                                    max = Math.max(max, count)
                                }
                                if (unknown_codes.length > 0) {
                                    console.warn("unknown codes: ", unknown_codes.join(" "), cn)
                                }
                                //data.sort((a, b) => a.value - b.value)
                                $dashboard_locals.advanced_req_map_echarts.base.setOption({
                                    visualMap: {
                                        max
                                    },
                                    series: [{
                                        data: Object.entries(resp_data).map(([name, value]) => {
                                            return {
                                                name,
                                                value
                                            }
                                        })
                                    }]
                                })
                            }
                        })
                    })
                    var map_rank = createElement("div")
                    var container = Tools.createFlexElement().append(
                        map_container,
                        map_rank
                    ).child("75%", "25%").classes("map-container")
                    $dashboard_locals.advanced_geo_switch = (new SwitchElement()).addButtons(
                        "req_map.world",
                        "req_map.china"
                    ).addEventListener("change", (event) => {
                        var data = event.detail
                        var type = data.button.slice("req_map.".length)
                        $dashboard_locals.advanced_req_map_echarts.base.setOption({
                            series: [{
                                map: type
                            }]
                        })

                    }).select(0)
                    panel.classes("label-text").append(
                        createElement("p").classes("title", "flex-between").append(
                            createElement("p").i18n(`dashboard.title.req_map`),
                            $dashboard_locals.advanced_geo_switch
                        ),
                        container
                    )
                    var observer = new ResizeObserver(() => {
                        var height = calcElementHeight(container)
                        map_container.style("min-height", `${height}px`)
                        $dashboard_locals.advanced_req_map_echarts.echart.resize()
                    })
                    observer.observe(panel.origin)
                })
                $dashboard_locals.advanced_qps = create_qps("advanced", req_section, req_map)
                $dashboard_locals.advanced_ip_access = Tools.createPanel(({ panel }) => {
                    var instance = Tools.createEchartElement((e) => {
                        $dashboard_locals.advanced_ip_access_echarts = e
                    })
                    panel.classes("label-text").append(
                        createElement("p").classes("title").i18n("dashboard.title.ip_access"),
                        instance
                    )
                    instance.style("min-height", "180px")
                    var observer = new ResizeObserver(() => {
                        $dashboard_locals.advanced_ip_access_echarts.echart.resize()
                    })
                    observer.observe(panel.origin)
                })

                advanced.push(
                    req_section.append(
                        req_map,
                        createElement("div").append(
                            $dashboard_locals.advanced_qps,
                            $dashboard_locals.advanced_ip_access
                        )
                    )
                )
            })();
            
            const init_echarts = () => {
                // basic
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
                    $dashboard_locals.basic_qps_echart,
                    $dashboard_locals.advanced_qps_echart
                ]
                for (let qps of instances) {
                    qps.base.setOption(option)
                    qps.base.showLoading()
                }

                for (const instance of Object.values($dashboard_locals.storage_echarts)) {
                    var option = {
                        color: [
                            $style.getThemeValue("echarts-color-0"),
                        ],
                        tooltip: {
                            trigger: 'axis'
                        },
                        grid: {
                            left: '4%',
                            right: '4%',
                            bottom: '2%',
                            top: '20%',
                            containLabel: true
                        },
                        xAxis: {
                            type: 'category',
                        },
                        yAxis: {
                            type: 'value',
                            min: 1,
                        },
                        series: []
                    };
                    instance.base.setOption(option)
                    instance.base.showLoading()
                }

                // pro

                option = {
                    yAxis: [
                        {
                            type: "value",
                            show: false
                        }
                    ],
                    tooltip: {
                        trigger: "axis",
                    },
                    xAxis: [
                        {
                            type: "category",
                            show: false,
                        }
                    ],
                    stateAnimation: {
                        duration: 300,
                        easing: "cubicOut"
                    },
                    grid: [
                        {
                            top: 5,
                            bottom: 20,
                            right: 0,
                            left: 0,
                            show: false,
                            z: 0,
                            containLabel: false,
                            backgroundColor: "rgba(0,0,0,0)",
                            borderWidth: 1,
                            borderColor: "#ccc"
                        }
                    ],
                    series: [
                        {
                            name: $i18n.t("dashboard.title.ip_access"),
                            type: "line",
                            symbol: "none",
                            data: [],
                            smooth: true,
                            lineStyle: {
                                width: 3,
                                color: {
                                    type: "linear",
                                    x: 0,
                                    y: 0,
                                    x2: 0,
                                    y2: 1,
                                    global: false,
                                    colorStops: [{ offset: 0, color: $style.getThemeValue("echarts-main-line-color") }, { offset: 1, color: $style.getThemeValue("echarts-dark-color") }]
                                },
                                type: "solid"
                            },
                            itemStyle: { borderRadius: [2, 2, 0, 0] },
                            z: 3,
                        }
                    ]
                }
                $dashboard_locals.advanced_ip_access_echarts.base.setOption(option)
                $dashboard_locals.advanced_ip_access_echarts.base.showLoading()

                option = {
                    tooltip: {
                        trigger: 'item',
                    },
                    visualMap: {
                        min: 0,
                        max: 100,
                        inRange: {
                            color: [$style.getThemeValue("echarts-none-color"), $style.getThemeValue("echarts-main-color")]
                        },
                        textStyle: {
                            color: $style.getThemeValue("echarts-main-color")
                        },
                        orient: 'horizontal',
                    },
                    series: {
                        type: 'map',
                        map: 'world',
                        itemStyle: {
                            normal: {
                                areaColor: $style.getThemeValue("echarts-area-color"),//'#F7F8FA',
                                borderColor: $style.getThemeValue("echarts-border-color")//'#CCC'
                            },
                            emphasis: {
                                areaColor: $style.getThemeValue("echarts-emphasis-color"),//'#ADD8E6',
                                borderColor: $style.getThemeValue("dark-color")//'#ffffff'
                            }
                        },
                        name: $i18n.t("dashboard.access"),
                        data: [],
                    }
                }
                $dashboard_locals.advanced_req_map_echarts.base.setOption(option)


            }
            // share 
            (() => {
                const config = {
                    "basic": 35,
                    "advanced": 35
                }
                $dashboard_locals.qps_data = ref({}, {
                    timeout: 20,
                    handler: (object) => {
                        for (let [key, count] of Object.entries(config)) {
                            const instance = $dashboard_locals[`${key}_qps_echart`]
                            const counter = $dashboard_locals[`${key}_qps_counter`]
                            var resp = object.object.resp;
                            var length = Object.keys(resp).length;
                            var keys = Object.keys(resp).slice(length - count);
                            var values = Object.values(resp).slice(length - count);
                            var option = {
                                color: $style.getThemeValue("echarts-color-0"),
                                xAxis: {
                                    data: keys
                                },
                                series: [{ name: 'QPS', data: values}]
                            }
                            instance.base.setOption(option)
                            counter.value = Object.values(resp).slice(length - 1)[0]
                        }
                    }
                })
                $dashboard_locals.qps_task = Tools.runTask(setInterval, async () => {
                    var resp = await $channel.send("qps")
                    $dashboard_locals.qps_data.resp = resp;
                }, 5000)
                window.addEventListener(THEMECHANGEEVENT, () => {
                    $dashboard_locals.qps_data.resp = $dashboard_locals.qps_data.resp;
                    $dashboard_locals.storage_data.refresh = true;
                    $dashboard_locals.advanced_req_map_echarts_data.refresh = true;
                })
            })();

            const reset_display = () => {
                $dashboard_locals.info_runtime.value = Tools.formatTime(0)
                $dashboard_locals.status.value = $i18n.t(`dashboard.value.status.default`, {})
                $dashboard_locals.files_info_30days_bytes.value = Tools.formatBytes(0)
                $dashboard_locals.files_info_30days_hits.value = Tools.formatSimpleNumber(0)
                $dashboard_locals.files_info_today_bytes.value = Tools.formatBytes(0)
                $dashboard_locals.files_info_today_hits.value = Tools.formatSimpleNumber(0)

                $dashboard_locals.system_info_connection.value = Tools.formatSimpleNumber(0)
                $dashboard_locals.system_info_cpu.value = Tools.formatSimpleNumber(0)
                $dashboard_locals.system_info_cpu_load.value = "0.0%"
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
                    for (let i = 1; i < $dashboard_locals.pre_switch.children.length; i++) {
                        $dashboard_locals.pre_switch.removeChild($dashboard_locals.pre_switch.children[i])
                    }
                    if (event.detail.index == 0) {
                        $dashboard_locals.container.append(
                            ...$dashboard_locals.basic
                        )
                        clearInterval($dashboard_locals.statistics_task)
                        $dashboard_locals.statistics_task = Tools.runTask(setInterval, async () => {
                            // 并发获取
                            const responses = {}
                            for (const key of ["storage_statistics_daily", "cluster_statistics_daily", "storage_statistics_hourly", "cluster_statistics_hourly", "storage_keys", "clusters_name"])
                                responses[key] = await $channel.send(key);
        
                            // set fileinfo 
                            var temp_response = {};
                            for (const statistics_type of ["storage", "cluster"]) {
                                for (const time_type of ["hourly", "daily"]) {
                                    const data = responses[`${statistics_type}_statistics_${time_type}`]
                                    // delete without "null" and "None"
                                    for (const delete_key of ["null", "None"]) {
                                        delete data[delete_key]
                                    }
                                    for (const [key, values] of Object.entries(data)) {
                                        var rdata = {};
                                        for (const value of values) {
                                            if (rdata[value._] === undefined) rdata[value._] = {}
                                            for (const key of ["hits", "bytes"]) {
                                                rdata[value._][key] = (rdata[value._][key] || 0) + value[key]
                                            }
                                        }
                                        if (temp_response[statistics_type] === undefined) temp_response[statistics_type] = {}
                                        if (temp_response[statistics_type][key] === undefined) temp_response[statistics_type][key] = {}
                                        temp_response[statistics_type][key][time_type] = rdata
                                        if (temp_response[statistics_type][":all:"] === undefined) temp_response[statistics_type][":all:"] = {}
                                        if (temp_response[statistics_type][":all:"][time_type] === undefined) temp_response[statistics_type][":all:"][time_type] = {}
                                        for (const [time, value] of Object.entries(rdata)) {
                                            for (const key of ["hits", "bytes"]) {
                                                if (temp_response[statistics_type][":all:"][time_type][time] === undefined) temp_response[statistics_type][":all:"][time_type][time] = {}
                                                temp_response[statistics_type][":all:"][time_type][time][key] = (temp_response[statistics_type][":all:"][time_type][time][key] || 0) + value[key]
                                            }
                                        }
                                    }
                                }
                            }
                            (() => {
                                var hourly = responses.cluster_statistics_hourly
                                var daily = responses.cluster_statistics_daily
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
                                         handler: Tools.formatUnitNumber,
                                         obj: 'today_hits',
                                         data: rdata.hourly_hits
                                    },
                                    {
                                         handler: Tools.formatUnitNumber,
                                         obj: '30days_hits',
                                         data: rdata.daily_hits
                                    },
                                    {
                                         handler: Tools.formatBytes,
                                         obj: 'today_bytes',
                                         data: rdata.hourly_bytes
                                    },
                                    {
                                        handler: Tools.formatBytes,
                                        obj: '30days_bytes',
                                        data: rdata.daily_bytes
                                    }
                                ]) {
                                    var formatted = handler(data)
                                    var o = $dashboard_locals[`files_info_${obj}`]
                                    var label = $dashboard_locals[`files_info_${obj}_label`]
                                    o.value = formatted
                                    if (label == undefined) continue
                                    label.value = data
                                }
                            })();
                            for (const [statistics_type, data] of Object.entries(temp_response)) {
                                $dashboard_locals.storage_data[statistics_type] = data
                            }
                            var t = {}
                            for (const {id, data} of responses.storage_keys) {
                                t[id] = data
                            }
                            $dashboard_locals.statistics_key_data.clusters = responses.clusters_name
                            $dashboard_locals.statistics_key_data.storages = t
                        }, 30000)
                        clearInterval($dashboard_locals.basic_task_system_info)
                        $dashboard_locals.basic_task_system_info = Tools.runTask(setInterval, async () => {
                            var resp = await $channel.send("systeminfo")
                            $dashboard_locals.system_info_connection.value = resp.connection.tcp + resp.connection.udp
                            $dashboard_locals.system_info_memory.value = Tools.formatBytes(resp.memory)
                            $dashboard_locals.system_info_cpu.value = resp.cpu.toFixed(1) + "%"
                            $dashboard_locals.system_info_cpu_load.value = resp.loads.toFixed(1) + "%"
                        }, 1000)

                    } else {
                        $dashboard_locals.container.append(
                            ...$dashboard_locals.advanced
                        )
                        $dashboard_locals.pre_switch.append(
                            $dashboard_locals.advanced_time_switch
                        )
                        $dashboard_locals.advanced_task = Tools.runTask(
                            setInterval, () => {
                                $dashboard_locals.advanced_task_trigger.value = ''
                            }, 10000
                        )
                    }
                    requestAnimationFrame(() => {
                        if ($dashboard_locals.qps_data.resp)
                            $dashboard_locals.qps_data.resp = $dashboard_locals.qps_data.resp;
                    })
                }).select(1)
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
        $dashboard_locals.basic_qps_echart.base.clear()
        $dashboard_locals.advanced_qps_echart.base.clear()
        for (const instance of Object.values($dashboard_locals.storage_echarts)) {
            instance.base.clear()
        }
    }

    const clearDashboardTask = (all = false) => {
        const $dashboard_locals = $menu_variables.dashboard;
        if (!$dashboard_locals) return;
        clearInterval($dashboard_locals.basic_task_system_info)
        clearInterval($dashboard_locals.statistics_task)
        clearInterval($dashboard_locals.advanced_task)
        if (!all) return;
        clearInterval($dashboard_locals.info_runtime_task)
        clearInterval($dashboard_locals.qps_task)
    }

    $router.beforeHandler(() => {
        while ($main.firstChild != null) {
            $main.removeChild($main.firstChild)
        }
        //clearDashboardTask(true)
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
        //$container.style("height", `${height}px`)
        $menu.style("top", `${header}px`)
        $main.style("margin-top", `${header}px`)
        $main.styleProperty("--height", `${header}px`)
    });
    observer.observe($app.origin, { childList: true, subtree: true });
    observer.observe($container.origin, { childList: true, subtree: true });

    $router.init()

}
window.addEventListener("DOMContentLoaded", async () => {
    echarts.registerMap('world', echarts_world)
    echarts.registerMap('china', echarts_china)
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