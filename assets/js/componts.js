import { app, CTElement, raf } from './cttb.js'


var cardTextOptions = {
    title: "text:title",
    value: "text:value",
}
var cardTextStyled = false;
const CTMenuDefaultOptions = {
    icon: null,
    title: 'text:default',
    children: []
}
const CTMenuOptions = {
    width: '232px',
    transition: 'all .3s ease-in-out',
}
var cardStyled = false;
var cardOptions = {
    withPadding: true,
    withMargin: true,
    handler: (element) => { }
}
var flexOptions = {
    gap: '0px',
    width: {
    }
}
export class CTAlert extends CTElement {
    static types = {
        info: "info",
        success: "success",
        warning: "warning",
        error: "error",
    }
    static defaultOptions = {
        type: CTAlert.types.info,
        message: "",
        duration: 3000,
    }
    constructor() {
        super("div").classes("c-alerts");
        this.alerts = [];
        app.body.append(this);

        app.style.addStyles({
            ".c-alerts": {
                "position": "fixed",
                "z-index": "999999",
                "width": "100%",
                "height": "0px",
                "top": "0",
                "display": "flex",
                "flex-direction": "column",
                "align-items": "center",
            },
            ".c-alerts .c-alert": {
                "position": "relative",
                "height": "0px",
                "width": "240px",
                "display": "flex",
                "align-items": "center",
                "height": "32px",
                "padding": "4px 8px 4px 8px",
                "border-radius": "4px",
                "margin-top": "16px",
                "z-index": "9999999",
                "transform": "translateY(-150%)",
                "transition": "transform 500ms cubic-bezier(0.4, 0, 0.2, 1), opacity 500ms cubic-bezier(0.4, 0, 0.2, 1), height 500ms cubic-bezier(0.4, 0, 0.2, 1), top 500ms cubic-bezier(0.4, 0, 0.2, 1)",
                "opacity": "0",
                "top": "0",
                "cursor": "pointer",
            },
            ".c-alerts .c-alert.show": {
                "transform": "translateY(0)",
                "opacity": "1",
                "height": "32px",
            },
            ".c-alerts .c-alert.leave": {
                "transform": "translateY(-150%)",
                "opacity": "0",
                "height": "0px",
            },
            ".c-alerts .c-alert svg": {
                "width": "14px",
                "height": "14px",
                "margin-right": "1px",
            },
            ".c-alerts .c-alert span": {
                "width": "100%",
                "font-size": "14px",
                "font-weight": "500",
                "line-height": "1.5",
                "text-align": "center",
            },
            ".c-alerts .c-alert.info": {
                "background-color": "#e0f7fa",
                "color": "#018786",
                "fill": "#018786",
                "box-shadow": "0px 3px 1px -2px rgb(0 135 130 / 20%), 0px 2px 2px 0px rgb(0 135 130 / 14%), 0px 1px 5px 0px rgb(0 135 130 / 12%)"
            },
            ".c-alerts .c-alert.success": {
                "background-color": "#e8f5e9",
                "color": "#1b5e20",
                "fill": "#1b5e20",
                "box-shadow": "0px 3px 1px -2px rgb(27 94 32 / 20%), 0px 2px 2px 0px rgb(27 94 32 / 14%), 0px 1px 5px 0px rgb(27 94 32 / 12%)"
            },
            ".c-alerts .c-alert.warning": {
                "background-color": "#fff3e0",
                "color": "#827717",
                "fill": "#827717",
                "box-shadow": "0px 3px 1px -2px rgb(130 119 23 / 20%), 0px 2px 2px 0px rgb(130 119 23 / 14%), 0px 1px 5px 0px rgb(130 119 23 / 12%)"
            },
            ".c-alerts .c-alert.error": {
                "background-color": "#ffebee",
                "color": "#b71c1c",
                "fill": "#b71c1c",
                "box-shadow": "0px 3px 1px -2px rgb(183 28 28 / 20%), 0px 2px 2px 0px rgb(183 28 28 / 14%), 0px 1px 5px 0px rgb(183 28 28 / 12%)"
            }
        })
    }
    addAlert(
        options = defaultOptions
    ) {
        let merged = { ...CTAlert.defaultOptions, ...options };
        this.render(merged);
    }
    render(options) {
        let alert = CTElement.create("div").classes("c-alert").classes(options.type);
        if (CTSVG[options.type] != undefined) {
            alert.append(CTSVG[options.type]);
        }
        alert.append(CTElement.create("span").text(options.message))
        alert.listener("click", () => {
            alert.remove()
        })
        super.append(alert);
        raf(() => {
            alert.classes("show");
            setTimeout(() => {
                alert.classes("leave")
                alert.listener("transitionend", () => {
                    alert.remove();
                }, {
                    once: true
                })
            }, options.duration)
        })
    }
    calcTop() {
        let top = 0;
        if (this.alerts.length > 0) {
            top = this.alerts[this.alerts.length - 1].$base.offsetHeight;
        }
        return top;
    }
}
export class CTSVG {
    static _parse(element) {
        return CTElement.create(document.createRange().createContextualFragment(element).childNodes[0]);
    }
    static get error() {
        return CTSVG._parse('<svg viewBox="64 64 896 896"><path d="M512 64c247.4 0 448 200.6 448 448S759.4 960 512 960 64 759.4 64 512 264.6 64 512 64zm127.98 274.82h-.04l-.08.06L512 466.75 384.14 338.88c-.04-.05-.06-.06-.08-.06a.12.12 0 00-.07 0c-.03 0-.05.01-.09.05l-45.02 45.02a.2.2 0 00-.05.09.12.12 0 000 .07v.02a.27.27 0 00.06.06L466.75 512 338.88 639.86c-.05.04-.06.06-.06.08a.12.12 0 000 .07c0 .03.01.05.05.09l45.02 45.02a.2.2 0 00.09.05.12.12 0 00.07 0c.02 0 .04-.01.08-.05L512 557.25l127.86 127.87c.04.04.06.05.08.05a.12.12 0 00.07 0c.03 0 .05-.01.09-.05l45.02-45.02a.2.2 0 00.05-.09.12.12 0 000-.07v-.02a.27.27 0 00-.05-.06L557.25 512l127.87-127.86c.04-.04.05-.06.05-.08a.12.12 0 000-.07c0-.03-.01-.05-.05-.09l-45.02-45.02a.2.2 0 00-.09-.05.12.12 0 00-.07 0z"></path></svg>')
    }
    static get loading() {
        return CTSVG._parse('<svg width="1em" height="1em" viewBox="0 0 1024 1024"><path d="M988 548c-19.9 0-36-16.1-36-36 0-59.4-11.6-117-34.6-171.3a440.45 440.45 0 00-94.3-139.9 437.71 437.71 0 00-139.9-94.3C629 83.6 571.4 72 512 72c-19.9 0-36-16.1-36-36s16.1-36 36-36c69.1 0 136.2 13.5 199.3 40.3C772.3 66 827 103 874 150c47 47 83.9 101.8 109.7 162.7 26.7 63.1 40.2 130.2 40.2 199.3.1 19.9-16 36-35.9 36z"></path></svg>')
    }
    static get loaded_success() {
        return CTSVG._parse('<svg width="1em" height="1em" viewBox="64 64 896 896"><path d="M699 353h-46.9c-10.2 0-19.9 4.9-25.9 13.3L469 584.3l-71.2-98.8c-6-8.3-15.6-13.3-25.9-13.3H325c-6.5 0-10.3 7.4-6.5 12.7l124.6 172.8a31.8 31.8 0 0051.7 0l210.6-292c3.9-5.3.1-12.7-6.4-12.7z"></path><path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"></path></svg>')
    }
    static get moon() {
        return CTSVG._parse('<svg width="24" height="24" viewBox="0 0 24 24"><path d="M12 11.807A9.002 9.002 0 0 1 10.049 2a9.942 9.942 0 0 0-5.12 2.735c-3.905 3.905-3.905 10.237 0 14.142 3.906 3.906 10.237 3.905 14.143 0a9.946 9.946 0 0 0 2.735-5.119A9.003 9.003 0 0 1 12 11.807z"></path></svg>')
    }
    static get sun() {
        return CTSVG._parse('<svg width="24" height="24" viewBox="0 0 24 24"><path d="M6.995 12c0 2.761 2.246 5.007 5.007 5.007s5.007-2.246 5.007-5.007-2.246-5.007-5.007-5.007S6.995 9.239 6.995 12zM11 19h2v3h-2zm0-17h2v3h-2zm-9 9h3v2H2zm17 0h3v2h-3zM5.637 19.778l-1.414-1.414 2.121-2.121 1.414 1.414zM16.242 6.344l2.122-2.122 1.414 1.414-2.122 2.122zM6.344 7.759 4.223 5.637l1.415-1.414 2.12 2.122zm13.434 10.605-1.414 1.414-2.122-2.122 1.414-1.414z"></path></svg>')
    }
    static get defaultSVG() {
        return CTSVG._parse('<svg width="24" height="24" viewBox="0 0 24 24"><path></path></svg>')
    }
    static get menu() {
        return CTSVG._parse('<svg width="24" height="24" viewBox="0 0 24 24"><path d="M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z"></path></svg>')
    }
    static get arrowdown() {
        return CTSVG._parse('<svg width="24" height="24" viewBox="0 0 24 24"><path d="M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z"></path></svg>')
    }
    static get iconDashboard() {
        return CTSVG._parse('<svg width="24" height="24" viewBox="0 0 1024 1024"><path d="M950.613333 475.562667c40.448 0 73.301333 32.682667 73.301334 73.045333V1024H731.306667V548.693333c0-40.362667 32.682667-73.130667 73.045333-73.130666h146.261333zM585.216 0c40.192 0 72.96 32.682667 72.96 72.96V1024H365.824V73.216A73.045333 73.045333 0 0 1 438.528 0h146.602667zM219.306667 292.693333a72.96 72.96 0 0 1 73.216 72.874667V1024H0V365.824c0-40.362667 32.682667-73.045333 73.045333-73.216H219.306667z m701.013333 268.202667h-85.248a18.346667 18.346667 0 0 0-18.346667 18.090667v359.765333h121.856V579.157333a18.261333 18.261333 0 0 0-18.261333-18.261333zM554.581333 85.333333h-85.333333a18.346667 18.346667 0 0 0-18.090667 18.261334V938.666667h121.6V103.594667A18.261333 18.261333 0 0 0 554.581333 85.333333zM181.76 378.026667H110.933333a25.6 25.6 0 0 0-25.6 25.6V938.666667h122.026667V403.626667a25.6 25.6 0 0 0-25.6-25.6z"></path></svg>')
    }
}
export class CTMenu extends CTElement {
    constructor(
        options = CTMenuOptions
    ) {
        super("div").classes("ct-menu").append(
            CTElement.create("h2").text("test")
        )
        
        let merged = Object.assign({}, CTMenuOptions, options)

        app.style.addStyles({
            ".ct-menu": {
                "position": "fixed",
                "width": merged.width,
                "height": "100%",
                "transition": `transform ${merged.transition}, opacity ${merged.transition}`,
                "transform": "translateX(0%)",
                "opacity": "1",
                "padding": "12px 16px",
                "background": "var(--background)"
            },
            ".ct-menu.action": {
                "transform": "translateX(-100%)",
                "opacity": "0",
            },
            ".ct-menu-item": {
                "display": "flex",
                "align-items": "center",
                "padding": "8px 0",
                "cursor": "pointer",
                "border-radius": "8px",
                "justify-content": "space-between",
                "color": "var(--color)",
                "fill": "var(--color)",
                "transition": "all var(--transition)",
            },
            ".ct-menu-item-l": {
                "margin-left": "8px",
                "display": "flex",
                "align-items": "center",
                "gap": "8px"
            },
            ".ct-menu-item:hover": {
                "color": "var(--main-color)",
                "fill": "var(--main-color)",
            },
            ".ct-menu-item-icon": {
                "width": "16px",
                "height": "16px",
            },
            ".ct-menu-item-arrow": {
                "width": "20px",
                "height": "20px",
                "transform": "rotate(-90deg)",
                "transition": "transform var(--transition)"
            },
            ".ct-menu-item.active .ct-menu-item-arrow": {
                "transform": "rotate(0deg)"
            },
            ".ct-menu-item.active": {
                "color": "var(--dark-color)",
                "fill": "var(--dark-color)",
                "background": "var(--main-color)"
            },
            ".ct-menu-sub-items": {
                "width": "100%",
                "height": "0px",
                "overflow": "hidden",
                "transition": "height var(--transition)",
                "color": "var(--color)",
            },
            ".ct-menu-sub-item": {
                "padding-left": "12px",
                "display": "flex",
                "align-items": "center",
                "cursor": "pointer",
                "height": "32px"
            },
            ".ct-menu-sub-item-icon": {
                "background": "var(--color)",
                "width": "6px",
                "height": "6px",
                "border-radius": "100%",
                "margin-right": "8px",
                "font-size": "10px",
            },
            ".ct-menu-sub-item:hover": {
                "color": "var(--color)"
            },
            ".ct-menu-sub-item.active": {
                "color": "var(--color)",
                "font-weight": "bold"
            },
            ".ct-menu-sub-item.active .ct-menu-sub-item-icon": {
                "background": "var(--main-color)",
                "width": "8px",
                "height": "8px",
                "margin-right": "7px",
                "margin-left": "-1px"
            }
        })

        this._containers = [];

        this._routed = false;
        app.router.beforeHandler((event) => {
            if (this._routed) return;
            this._routed = true;
            var path = event.currentRoute;
            var eidx = null;
            var cidx = null;
            this._containers.forEach((option, idx) => {
                if (!path.startsWith(option.key)) return;
                eidx = idx;
                if (option.children.length == 0) return;
                let p = path.slice(option.key.length);
                option.children.forEach((child, idx) => {
                    if (!child.key.startsWith(p)) return;
                    cidx = idx;
                })
            })
            raf(() => {
                if (eidx != null) this.clickItem(eidx);
                if (cidx != null) this.clickSubItem(eidx, cidx);
            })
        })
    }
    add(options = CTMenuDefaultOptions) {
        let merged = Object.assign({}, CTMenuDefaultOptions, options)
        this._containers.push(
            merged
        )
        this.render();
    }
    _setTitle(element, title) {
        let [type, text] = [title.slice(0, title.indexOf(":")), title.slice(title.indexOf(":") + 1)];
        console.log(type, text)
        if (type == "text") {
            element.text(text)
        } else if (type == "i18n") {
            element.i18n(text);
        } else {
            element.text(title)
        }
        return element;
    }
    render() {
        if (this._renderTask) return;
        this._renderTask = raf(() => {
            this._renderTask = null;
            
            this.clear();

            this._containers.forEach((options, idx) => {
                var {
                    icon,
                    title,
                    children,
                    key
                } = options;

                if (icon == null) {
                    icon = CTSVG.defaultSVG;
                }
                var item = CTElement.create("div").classes("ct-menu-item").append(
                    CTElement.create("div").classes("ct-menu-item-l").append(
                        icon.classes("ct-menu-item-icon"),
                        setTitle(CTElement.create("div").classes("ct-menu-item-title"), title),
                    )
                ).listener("click", () => {
                    this.clickItem(idx)
                }).attr("link", key)
                this.append(item)
                if (children.length == 0) {
                    return;
                }
                item.append(CTSVG.arrowdown.classes("ct-menu-item-arrow"))
                var subitem = CTElement.create("div").classes("ct-menu-sub-items");
                children.forEach((child, child_idx) => {
                    subitem.append(
                        CTElement.create("div").classes("ct-menu-sub-item").append(
                            CTElement.create("span").classes("ct-menu-sub-item-icon"),
                            setTitle(CTElement.create("span"), child.title)
                        ).attr("link", child.key).listener("click", () => {
                            this.clickSubItem(idx, child_idx)
                        })
                    )
                })
                this.append(subitem)
            })
        });
    }
    getElements() {
        var elements = [];
        var children = {}
        for (var i = 0; i < this.children.length; i++) {
            let element = this.children[i];
            if (element.hasClasses("ct-menu-item")) {
                elements.push(element)
            } else if (element.hasClasses("ct-menu-sub-items")) {
                children[elements.findIndex((e) => e == this.children[i - 1])] = element;
            }
        }
        return {
            elements,
            children
        }
    }
    clickItem(idx) {
        var {
            elements,
            children
        } = this.getElements();
        elements.forEach((element) => {
            element.removeClasses("active")
        })
        Object.values(children).forEach((element) => {
            element.style("height", "0px")
            element.children.forEach((e) => {
                e.removeClasses("active")
            })

        })
        // then add active
        var element = elements[idx];
        element.classes("active")
        if (!(idx in children)) {
            app.route(element.attr("link"))
            return;
        }
        var subitem = children[idx];

        raf(() => {
            subitem.style("height", "auto")

            var height = subitem.boundingClientRect.height;

            subitem.style("height", "0px")
            subitem.style("height", `${height}px`)
        })
        var subitems = subitem.children;
        if (subitems.length > 0) {
            subitems[0].click()
        }
    }
    clickSubItem(idx, child_idx) {
        var {
            elements,
            children
        } = this.getElements();
        Object.values(children).forEach((element) => {
            element.children.forEach((e) => {
                e.removeClasses("active")
            })
        })
        var element = elements[idx];
        var subitem = children[idx].children[child_idx];
        subitem.classes("active")
        var parent_link = element.getattr("link"), child_link = subitem.getattr("link");
        app.route(`${parent_link}${child_link}`)
    }
    toggle() {
        super.ctoggle("action")
    }
}
export function CTCard(options = cardOptions) {
    let merged = Object.assign({}, cardOptions, options)
    let element = CTElement.create("div").classes("ct-card")
    if (!cardStyled) {
        cardStyled = true;
        app.style.addStyles({
            ".ct-card": {
                "border-radius": "4px",
                "background": "var(--card-bg-color)"
            },
            ".ct-card-padding": {
                "padding": "24px"
            },
            ".ct-pre-card": {
                "padding-left": "24px",
                "padding-top": "24px"
            }
        })
    }
    if (merged.withPadding) {
        element.classes("ct-card-padding")
    }
    merged.handler(element)
    if (merged.withMargin) {
        element = CTElement.create("div").classes("ct-pre-card").append(element);
    }
    return element;
}
export function CTCardText(options = cardTextOptions) {
    let merged = Object.assign({}, cardTextOptions, options)
    let titleElement = (CTElement.isDOM(merged.title) || merged.title instanceof CTElement) ? merged.title : CTElement.create("p").classes("ct-card-text-title");
    let valueElement = (CTElement.isDOM(merged.value) || merged.value instanceof CTElement) ? merged.value : CTElement.create("p").classes("ct-card-text-value");
    if (!cardTextStyled) {
        cardTextStyled = true;
        app.style.addStyles({
            ".ct-card-text-title": {
                "color": "var(--text-color)",
                "display": "flex",
                "align-items": "center",
                "font-size": "14px"
            },
        })
    }

    setTitle(titleElement, merged.title)
    setTitle(valueElement, merged.value)

    return [
        titleElement,
        valueElement
    ]
}
export class CTOptionBar extends CTElement {
    constructor() {
        super("div").classes("ct-option-bar")
        app.style.addStyles({
            ".ct-option-bar": {
                "display": "flex",
                "align-items": "center",
                "justify-content": "space-between",
                "border-bottom": "1px solid var(--border-color)"
            }
        })
    }
}
export class CTFlex extends CTElement {
    constructor(
        options = flexOptions
    ) {
        super("div").classes("ct-flex")

        this.options = Object.assign({}, flexOptions, options)

        app.style.addStyles({
            ".ct-flex": {
                "display": "flex",
                "flex-wrap": "wrap"
            }
        })

        this.style("gap", this.options.gap)

        this.observe = new ResizeObserver((entries) => {
            this.render();
        })
        this.observe.observe(this.base)
    }
    render() {
        if (this._renderTask != null) return;
        this._renderTask = raf(() => {
            this._renderTask = null;
            var rect = this.boundingClientRect;
            if (this.options.width == "auto" || !this.options.width) return;
            var widths = Object.entries(this.options.width).map(([a, b]) => [Number(a), Number(b)]).sort((a, b) => b[0] - a[0]);
            const totalWidth = rect.width;
            let childCount = null;
            for (let [width, count] of widths) {
                if (width >= totalWidth) {
                    childCount = count;
                }
            }
            childCount = childCount || this.children.length;
            var perwidth = totalWidth / childCount;
            for (let child of this.children) {
                child.style("width", perwidth + "px")
            }
        })
    }
}
function setTitle(element, title) {
    if (title == null || title instanceof CTElement || CTElement.isDOM(title)) {
        return element;
    }
    let [type, text] = [title.slice(0, title.indexOf(":")), title.slice(title.indexOf(":") + 1)];
    if (type == "text") {
        element.text(text)
    } else if (type == "i18n") {
        element.i18n(text);
    } else {
        element.text(title)
    }
    return element;
}