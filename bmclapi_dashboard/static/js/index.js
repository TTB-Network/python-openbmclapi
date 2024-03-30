(() => {
    const ttb = new TTB();
    const global_styles = {
        "body,ol,ul,h1,h2,h3,h4,h5,h6,p,th,td,dl,dd,form,fieldset,legend,input,textarea,select": "margin:0;padding:0",
        "body": "font:12px;background:#fff;-webkit-text-size-adjust:100%",
        "a": "color:#172c45;text-decoration:none",
        "em": "font-style:normal",
        "li": "list-style:none",
        "img": "border:0;vertical-align:middle",
        "table": "border-collapse:collapse;border-spacing:0",
        "p": "word-wrap:break-word",
        ":root": [
            "--r-main-background-color: #F6F7F9",
            "--r-background-color: #191919",
            "--r-main-font-size: 42px",
            "--r-main-color: #fff",
            "--r-block-margin: 20px",
            "--r-heading-margin: 0 0 20px 0",
            "--r-heading-font: Source Sans Pro, Helvetica, sans-serif",
            "--r-heading-color: #fff",
            "--r-heading-line-height: 1.2",
            "--r-heading-letter-spacing: normal",
            "--r-heading-text-transform: uppercase",
            "--r-heading-text-shadow: none",
            "--r-heading-font-weight: 600",
            "--r-heading1-text-shadow: none",
            "--r-heading1-size: 2.5em",
            "--r-heading2-size: 1.6em",
            "--r-heading3-size: 1.3em",
            "--r-heading4-size: 1em",
            "--r-code-font: monospace",
            "--r-link-color: #42affa",
            "--r-link-color-dark: #068de9",
            "--r-link-color-hover: #8dcffc",
            "--r-selection-background-color: rgba(66, 175, 250, .75)",
            "--r-selection-color: #fff",
            "--r-overlay-element-bg-color: 240, 240, 240",
            "--r-overlay-element-fg-color: 0, 0, 0",
            "--r-ligting-color: rgb(15, 198, 194);"
        ],
        ".root .left": [
            "position: fixed",
            "min-height: calc(100vh - 72px)",
            "max-height: calc(100vh - 72px)",
            "min-width: 48px",
            "max-width: 184px",
            "margin-top: 16px",
            "width: 256px",
            "padding: 8px",
            "padding-top: 0",
            "background: var(--r-main-background-color)",
            "transition: transform 200ms linear 0s;",
            "box-shadow: rgba(145, 158, 171, 0.2) 0px 4px 10px;"
        ],
        ".root .left .content": [
            "overflow: auto",
            "width: 95%"
        ],
        ".root .left.hide": [
            "transform: translateX(-100%);",
        ],
        ".root .left .button": [
            "cursor: pointer;",
            "border-radius: 8px;",
            "margin-bottom: 8px",
            "padding: 4px",
            "padding-left: 8px",
            "transition: color 200ms linear 0s;",
        ],
        ".root .left .arrow-background": [
            "position: absolute",
            "background: var(--r-main-background-color)",
            "width: 20px",
            "height: 20px",
            "left: 194px",
            "margin-top: -16px",
            "cursor: pointer"
        ],
        ".root .left .arrow": [
            "width: 100%",
            "height: 100%",
            'background-image: url("data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgc3R5bGU9IndpZHRoOiAxZW07aGVpZ2h0OiAxZW07dmVydGljYWwtYWxpZ246IG1pZGRsZTtmaWxsOiBjdXJyZW50Q29sb3I7b3ZlcmZsb3c6IGhpZGRlbjsiIHZpZXdCb3g9IjAgMCAxMDI0IDEwMjQiIHZlcnNpb249IjEuMSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiBwLWlkPSI3NTUiPjxwYXRoIGQ9Ik0zMjUuMDQ4IDkzLjUxMWwtNjAuMDMwIDU5LjQzNSAzNTcuMTgxIDM1OS42MzEtMzYwLjE4NCAzNTYuNjAzIDU5LjUyMiA1OS45MyA0MjAuMjA3LTQxNi4wNDN6IiBmaWxsPSIjODQ4NDg0IiBwLWlkPSI3NTYiPjwvcGF0aD48L3N2Zz4=");',
        ],
        ".root .container .left.hide .arrow-background .arrow": [
            "transform: rotate(0deg);",
        ],
        ".root .container .left .arrow-background .arrow": [
            "transform: rotate(180deg);",
            "transition: transform 100ms linear 0s;",
        ],
        ".root .left .button:hover": [
            "color: var(--r-ligting-color)"
        ],
        ".root .left .button.selected": [
            "background: var(--r-ligting-color)",
            "box-shadow: rgba(15, 198, 194, 0.2) 0px 10px 25px 0px;",
            "color: white"
        ],
        ".root .left .side": [
            "margin-left: 8px",
        ],
        ".root .left .sidebutton": [
            "padding: 2px",
            "margin-bottom: 8px",
            "cursor: pointer;",
            "color: rgba(0, 0, 0, 0.5);",
            "transition: color 200ms linear 0s;",
        ],
        ".root .left .sidebutton:hover": [
            "color: var(--r-link-color-hover)"
        ],
        ".root .left .sidebutton.selected": [
            "color: black",
            "font-weight: bold",
        ],
        ".root .left .sidebutton:hover .cycle": [
            "background: var(--r-link-color-hover)"
        ],
        ".root .left .sidebutton.selected .cycle": [
            "width: 8px;",
            "height: 8px;",
            "background-color: rgb(15, 198, 194);",
            "margin-right: 6px",
            "margin-left: 2px",
            "border-radius: 50%;"
        ],
        ".root .left .sidebutton .cycle": [
            "width: 4px;",
            "height: 4px;",
            "margin: 4px",
            "margin-right: 8px",
            "background-color: rgba(0, 0, 0, 0.5);",
            "transition: background-color 200ms linear 0s;",
            "border-radius: 50%;"
        ],
        ".root .header": [
            "position: fixed",
            "height: 40px",
            "min-height: 40px",
            "min-width: calc(100% - 8px)",
            "background: var(--r-main-background-color)",
            "z-index: 1",
            "padding: 8px",
            "box-sizing: border-sizing",
            "box-shadow: rgba(145, 158, 171, 0.2) 0px 4px 10px;"
        ],
        ".root .container": [
            "position: relative;",
            "top: 56px;",
        ],
        ".root .container .right": [
            "padding-top: 16px",
            "margin-left: 216px",
            "transition: width 200ms linear 0s;",
            "min-width: calc(100vw - 232px)",
            "min-height: calc(100vh - 72px)",
        ],
        ".root .container .left.hide ~ .right": [
            "margin-left: 0",
            "min-width: 100vw",
        ],
        ".panel": [
            "background-color: rgb(255, 255, 255);",
            "color: rgb(0, 0, 0);",
            "transition: box-shadow 300ms cubic-bezier(0.4, 0, 0.2, 1) 0ms;",
            "border-radius: 4px;",
            "background-image: none;",
            "padding: 24px;",
            "box-shadow: rgba(145, 158, 171, 0.2) 0px 4px 10px;",
            "margin: 16px;",
        ],
        ".panel.info-4": [
            "display: flex",
            "flex-warp: warp"
        ],
        ".panel.info-4 div": [
            "width: 25%"
        ],
        ".panel.info-2": [
            "display: flex",
            "flex-warp: warp"
        ],
        ".panel.info-2 div": [
            "width: 50%"
        ],
        ".panel .title": [
            "display: flex",
            "margin: 0px 0px 6px;",
            "font-family: inherit;",
            "font-weight: 400;",
            "line-height: 1.5;",
            "color: rgba(0, 0, 0, 0.5);",
            "font-size: 14px;"
        ],
        ".panel .value": [
            "margin: 0px;",
            "font-family: inherit;",
            "font-weight: 400;",
            "line-height: 1.5;",
            "color: rgba(0, 0, 0, 0.7);",
            "font-size: 24px;",
        ],
        ".root .container .left.hide~.right": [
            "margin-left: 32px",
            "min-width: calc(100vw - 48px)"
        ],
        ".root .left .copyright": [
            "position: fixed;",
            "bottom: 2px",
        ],
        ".qps .icon": [
            "width: 14px",
            "height: 14px"
        ],
        ".qps": [
            "display: flex",
            "align-items: center"
        ],
        ".progress": [
            "position: absolute;",
            "z-index: 99999999999999999",
            "width: 0",
            "height: 2px",
            "background: var(--r-ligting-color)",
            "transition: width 200ms linear 0s;",
        ],
        "body": [
            "background-color: var(--r-main-background-color)"
        ],
        ".auth": [
            "display: flex",
            "flex-wrap: wrap",
            "justify-content: center"
        ],
        ".auth input[type=text], input[type=password]": [
            "outline: none",
            "width: 90%",
            "margin-top: 16px",
            "height: 2rem",
            "font-size: 1.2rem",
            "border: none",
            "padding: 8px 0 0 8px",
            "border-bottom: 1px solid var(--r-ligting-color)",
            "color: var(--r-ligting-color)",
            "background-color: rgba(0, 0, 0, 0)",
            "box-sizing: border-sizing"
        ],
        ".auth input[type=submit]": [
            "outline: none",
            "border: none",
            "width: 90%",
            "cursor: pointer",
            "padding: 8px 0 0 8px",
            "box-sizing: border-sizing",
            "margin-top: 16px",
            "font-size: 1.2rem",
            "height: 2.5rem",
            "background-color: rgba(0, 0, 0, 0)",
            "transition: color 200ms linear 0s, background-color 200ms linear 0s;",
        ],
        ".auth input[type=submit]:hover": [
            "color: var(--r-ligting-color)"
        ],
        ".auth input[type=submit]:active": [
            "background: var(--r-ligting-color)",
            "box-shadow: rgba(15, 198, 194, 0.2) 0px 10px 25px 0px;",
            "color: white"
        ]
    }
    const root = ttb.createElement("div").class("root")
    const header = ttb.createFlex().disable().class("header").style("align-items", "center").style("flex-wrap", "nowrap").style("justify-content", "space-between")
    const left = ttb.createElement("div").class("left")
    const left_arrow = ttb.createElement("div").class("arrow-background").append(ttb.createElement("div").class("arrow"))
    const left_content = ttb.createElement("div").class("content")
    const left_copyright = ttb.createElement("div").class("copyright")
    const container = ttb.createElement("div").class("right")
    const menu_data = {};  
    const progress = ttb.createElement("div").class("progress")
    const menu_variables = {}

    const set_progress = (val) => {
        progress.setStyle("width", (val * 100.0) + "%")
        if (val * 100.0 >= 99) setTimeout(() => progress.setStyle("width", 0), 250)
    }
    const menu = (key, icon, text, core) => {  
        const hasSubmenu = key.includes('.');  
        if (hasSubmenu) {
            const [mainKey, subKey] = [key.slice(0, key.indexOf(".")), key.slice(key.indexOf(".") + 1)]
            if (!menu_data[mainKey]) menu_data[mainKey] = { icon, children: [], text: '', core };
            if (!("children" in menu_data[mainKey])) menu_data[mainKey].children = [];
            menu_data[mainKey].children.push({ key: subKey, text, core });
        } else menu_data[key] = { key, icon, text, core };
    }
    const delete_menu = (key) => {
        const hasSubmenu = key.includes('.');  
        if (hasSubmenu) {
            const [mainKey, subKey] = [key.slice(0, key.indexOf(".")), key.slice(key.indexOf(".") + 1)]
            if (!menu_data[mainKey]) return
            menu_data[mainKey].children = menu_data[mainKey].children.filter(v => v.key != key)
        } else delete menu_data[key]
    }
    const display_left = () => {
        left_content.clear()
        //const show = !left.containsClass("hide")
        for (const key in menu_data) {
            const object = menu_data[key]
            const sub = !(!object.children)
            const div = ttb.createFlex().class("button").id("left-list-" + key).append(ttb.createElement("p").setText(object.text)).style("align-items", "center").height("32px").event("click", () => {
                window.location.hash = key + (sub ? "?key=" + object.children[0].key : "")
            })
            left_content.append(div)
            if (sub) {
                const sub_div = ttb.createElement("div").style("display: none").class("side").id("left-list-" + key + "-sub")
                for (const child of object.children) {
                    sub_div.append(ttb.createFlex().class("sidebutton").id("left-list-" + key + "-sub-" + child.key).append(ttb.createElement("div").class("cycle"), ttb.createElement("p").setText(child.text)).style("align-items", "center").height("32px").event("click", () => {
                        window.location.hash = key + (sub ? "?key=" + child.key : "")
                    }))
                }
                left_content.append(sub_div)
            }
        }
    }
    const update_left = () => {
        const key = ttb.getURLKey() || Object.keys(menu_data)[0]
        for (const bkey of Object.keys(menu_data)) {
            if (last_key != key) {
                if (bkey == key) {
                    document.getElementById("left-list-" + bkey).classList.add("selected")
                    last_key_b = ""
                } else document.getElementById("left-list-" + bkey).classList.remove("selected")
            } else if (last_key == bkey) document.getElementById("left-list-" + bkey).classList.add("selected")
            if (document.getElementById("left-list-" + bkey + "-sub")) {
                if (bkey == key) document.getElementById("left-list-" + bkey + "-sub").style.display = "block"
                else document.getElementById("left-list-" + bkey + "-sub").style.display = "none"
                const skey = ttb.getURLKeyParams()['key'] || Object.keys(Object.values(menu_data)[0])[1]
                for (const subkey of menu_data[bkey].children.map(v => v.key)) {
                    if (subkey == skey) {
                        document.getElementById("left-list-" + bkey + "-sub-" + subkey).classList.add("selected")
                        last_key_b = skey
                    } else document.getElementById("left-list-" + bkey + "-sub-" + subkey).classList.remove("selected")
                }
            }
        }
    }
    const popstate = () => {
        const key = ttb.getURLKey() || Object.keys(menu_data)[0]
        const last_key_sub = last_key_b
        update_left()
        if (last_key != key || (last_key_b && last_key_b != last_key_sub)) {
            if (last_key && (last_key_b && last_key_b == last_key_sub))
                handler(last_key, last_key_sub, "disconnect")
            handler(key, last_key_b, "connect")
        }
        last_key = key;
    }
    const handler = (root, key, type) => {
        const object = (key ? menu_data[root].children.filter(v => v.key == key)[0] : menu_data[root]).core || {}
        root += (key ? "-" + key : "")
        if (last_root != root) {
            if (last_root in object && "disconnect" in object) {
                try {
                    object["disconnect"]()
                } catch (e) {
                    console.log(e)
                }
            }
            while (document.getElementsByClassName("right")[0].firstChild != null)
                document.getElementsByClassName("right")[0].removeChild(document.getElementsByClassName("right")[0].firstChild)
            last_root = root
        }
        if (!(type in object)) {
            set_progress(1)
            return
        }
        try {
            document.getElementsByClassName("right")[0].style.display = 'none'
            page = []
            if (type == "connect" && "page" in object) {
                set_progress(0.7)
                if ("init" in object) object["init"]()
                set_progress(0.8)
                page = object["page"]() || []
            }
            set_progress(0.9)
            object[type](page)
            if (page != null)
                document.getElementsByClassName("right")[0].append(ttb.createElement("div").id("module-" + root).append(...(Array.isArray(page) ? page : [page])).valueOf())
            document.getElementsByClassName("right")[0].style.display = 'block'
            set_progress(1)
        } catch (e) {
            console.log(e)
        }
    }
    const root_handler = (func, ...data) => {
        var splited = last_root.split("-", 1)
        var root_ = splited[0], key_ = splited[1];
        const object = (key_ ? menu_data[root_].children.filter(v => v.key == key_)[0] : menu_data[root_]).core || {}
        if (func in object) object[func](...data)
    }
    let last_key = '';
    let last_key_b = '';
    let last_root = '';
    const resize = () => {
        display_left()
        update_left()
    }
    header.append(ttb.createElement("h3").setText("Python OpenBMCLAPI Dashboard"))
    left_copyright.append(
        ttb.createElement("p").append(ttb.createElement("a").setAttribute("href", "mailto:administrator@ttb-network.top").setText("TTB Network"), " - ", ttb.VERSION)
    )
    left_arrow.event("click", () => {
        left.toggle("hide")
        window.dispatchEvent(new Event('resize'));
    })
    if (window.outerWidth <= window.outerHeight * 1.25) left_arrow.valueOf().click()
    root.append(header, ttb.createElement("div").class("container").append(left.append(left_arrow, left_content, left_copyright), container))
    window.addEventListener("resize", resize)
    window.addEventListener("popstate", popstate)
    document.body.prepend(progress.valueOf(), root.valueOf());
    (() => {
        class Dashboard {
            constructor() {
                this.runtime = null
                this._page = [
                    ttb.createElement("div").class("panel").append(
                        ttb.createFlex().child(2).append(
                            ttb.createElement("div").append(
                                ttb.createElement("p").class("title").setText("运行时间"),
                                ttb.createElement("p").class("value").setText("-")
                            ),
                            ttb.createElement("div").append(
                                ttb.createElement("p").class("title").setText("状态"),
                                ttb.createElement("p").class("value").setText("-")
                            )
                        )
                    ),
                    ttb.createFlex().child(2).append(
                        ttb.createElement("div").append(
                            ttb.createElement("div").class("panel").append(
                                ttb.createFlex().child(4).append(
                                    ttb.createElement("div").append(
                                        ttb.createElement("p").class("title").setText("今日下载数"),
                                        ttb.createElement("p").class("value").setText("-")
                                    ),
                                    ttb.createElement("div").append(
                                        ttb.createElement("p").class("title").setText("今日下载量"),
                                        ttb.createElement("p").class("value").setText("-")
                                    ),
                                    ttb.createElement("div").append(
                                        ttb.createElement("p").class("title").setText("30 天内下载数"),
                                        ttb.createElement("p").class("value").setText("-")
                                    ),
                                    ttb.createElement("div").append(
                                        ttb.createElement("p").class("title").setText("30 天内下载量"),
                                        ttb.createElement("p").class("value").setText("-")
                                    )
                                ).minWidth(128)
                            ),
                            ttb.createElement("div").class("panel").append(
                                ttb.createFlex().child(4).append(
                                    ttb.createElement("div").append(
                                        ttb.createElement("p").class("title").setText("连接数"),
                                        ttb.createElement("p").class("value").setText("-")
                                    ),
                                    ttb.createElement("div").append(
                                        ttb.createElement("p").class("title").setText("内存使用"),
                                        ttb.createElement("p").class("value").setText("-")
                                    ),
                                    ttb.createElement("div").append(
                                        ttb.createElement("p").class("title").setText("文件缓存"),
                                        ttb.createElement("p").class("value").setText("-")
                                    ),
                                    ttb.createElement("div").append(
                                        ttb.createElement("p").class("title").setText("5 分钟负载"),
                                        ttb.createElement("p").class("value").setText("-")
                                    )
                                )
                            )
                        ),
                        ttb.createElement("div").class("panel").append(
                            ttb.createElement("p").class("title").append(ttb.createElement("span").setText("请求数 - 5 分钟内: ").append(
                                ttb.createElement("span")
                            )),
                            ttb.createElement("p").class("value").style("min-height: 162px;")
                        ),
                        ttb.createElement("div").class("panel").append(
                            ttb.createElement("p").class("title").setText("每小时下载数"),
                            ttb.createElement("p").class("value").style("min-height: 128px")
                        ),
                        ttb.createElement("div").class("panel").append(
                            ttb.createElement("p").class("title").setText("每小时下载量"),
                            ttb.createElement("p").class("value").style("min-height: 128px")
                        ),
                        ttb.createElement("div").class("panel").append(
                            ttb.createElement("p").class("title").setText("每天下载数"),
                            ttb.createElement("p").class("value").style("min-height: 128px")
                        ),
                        ttb.createElement("div").class("panel").append(
                            ttb.createElement("p").class("title").setText("每天下载量"),
                            ttb.createElement("p").class("value").style("min-height: 128px")
                        )
                    ).child(2).minWidth(896).addResize(() => {
                        this._e_bytes.resize();
                        this._e_daily_bytes.resize()
                        this._e_hits.resize()
                        this._e_daily_hits.resize()
                        this._e_qps.resize()
                    })
                ]
                this._updateTimer = setInterval(() => this.update(), 1000)
                this._e_options = {  
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
                this._unit_bytes = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]
                this._unit_number = ["", "k", "M", "G", "T", "P", "E"]
                this._hourly = Array.from({ length: 24 }, (_, i) => i + " 时")
                this._daily = Array.from({ length: 31 }, (_, i) => i + " 天")
                this._e_qps         = echarts.init(this._page[1].getChildrens()[1].getChildrens()[1].valueOf())
                this._e_hits        = echarts.init(this._page[1].getChildrens()[2].getChildrens()[1].valueOf())
                this._e_bytes       = echarts.init(this._page[1].getChildrens()[3].getChildrens()[1].valueOf())
                this._e_daily_hits  = echarts.init(this._page[1].getChildrens()[4].getChildrens()[1].valueOf())
                this._e_daily_bytes = echarts.init(this._page[1].getChildrens()[5].getChildrens()[1].valueOf())
                this._e_hits.setOption(this._e_options)
                this._e_bytes.setOption(this._e_options)
                this._e_hits.setOption({
                    xAxis: {  
                        data: this._hourly,
                    }, 
                })
                this._e_bytes.setOption({
                    xAxis: {  
                        data: this._hourly,
                    }, 
                })
                this._e_daily_hits.setOption(this._e_options)
                this._e_daily_bytes.setOption(this._e_options)
                this._e_daily_hits.setOption({
                    xAxis: {  
                        data: this._daily,
                    }, 
                })
                this._e_daily_bytes.setOption({
                    xAxis: {  
                        data: this._daily,
                    }, 
                })
                this._e_qps.setOption({
                    color: "#0fc6c2",
                    tooltip: {
                        trigger: 'axis',
                        formatter: e => '<div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="font-size:14px;color:#666;font-weight:400;line-height:1;">' + e[0].name + '</div><div style="margin: 10px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:#0fc6c2;"></span><span style="font-size:14px;color:#666;font-weight:400;margin-left:2px">QPS</span><span style="float:right;margin-left:20px;font-size:14px;color:#666;font-weight:900">Avg: ' + e[0].data.value + " total: " + ttb.sum(...e[0].data.raw) + '</span><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div>',
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
                })
                this.update()
                setTimeout(() => this._page[1].update(), 1)
            }
            connect(page) {
                page.push(...this._page)
            }
            update() {
                this._page[0].getChildrens()[0].getChildrens()[0].getChildrens()[1].setText(this._format_time(this.runtime, true))
            }
            updateStatus(text) {
                this._page[0].getChildrens()[0].getChildrens()[1].getChildrens()[1].setText(text)
            }
            _format_time(n, sub = false) {
                if (n == null) return "-"
                let seconds = Number.parseInt(n)
                if (sub) seconds = Number.parseInt(ttb.getTime() - seconds)
                return `${parseInt(seconds / 60 / 60 / 24).toString().padStart(2, '0')} 天 ${parseInt(seconds / 60 / 60 % 24).toString().padStart(2, '0')} 小时 ${parseInt(seconds / 60 % 60).toString().padStart(2, '0')} 分钟 ${parseInt(seconds % 60).toString().padStart(2, '0')} 秒`
            }
            _format_bytes(size, i = null) {
                if (size == 0) return `${size.toFixed(2)}${this._unit_bytes[0]}`
                i = i || Math.min(Number.parseInt(Math.floor(Math.log(size) / Math.log(1024))), this._unit_bytes.length)
                if (i <= 0) return `${size.toFixed(2)}${this._unit_bytes[0]}` 
                size = size / (1024 ** i)
                return `${size.toFixed(2)}${this._unit_bytes[i]}`
            }
            _e_templates(params, value_formatter = null) {
                const templates = `<div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:{color};"></span><span style="font-size:14px;color:#666;font-weight:400;margin-left:2px">{name}</span><span style="float:right;margin-left:20px;font-size:14px;color:#666;font-weight:900">{value}</span><div style="clear:both"></div></div><div style="clear:both"></div></div>`
                var template = ''
                for (const data of params) {
                    template += templates.replace("{color}", data.color).replace("{name}", data.name).replace("{value}", value_formatter ? value_formatter(data.value) : data.value)
                }
                return `<div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="font-size:14px;color:#666;font-weight:400;line-height:1;">${params[0].name}</div><div style="margin: 10px 0 0;line-height:1;">${template}</div><div style="clear:both"></div></div><div style="clear:both"></div></div>`
            }
            _format_number_unit(n) {
                var d = (n + "").split("."), i = d[0], f = d.length >= 2 ? "." + d.slice(1).join(".") : ""
                return i.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ", ") + f;
            }
            _e_format_time(n) {
                const date = new Date(n)
                return date.getHours().toString().padStart(2, 0) + ":" + date.getMinutes().toString().padStart(2, 0) + ":" + date.getSeconds().toString().padStart(2, 0)
            }
        }
        class MainWebSocket {
            constructor() {
                this.ws = ttb.websocket("ws" + (window.location.protocol.slice(4)) + "//" + window.location.host + window.location.pathname, {
                    "onopen": () => this.onopen(),
                    "onmessage": (msg) => {
                        let reader = new FileReader();
                        reader.onload = () => {
                            let arrayBuffer = reader.result;
                            const input = new DataInputStream(arrayBuffer)
                            this.message(input.readString(), this._deserializeData(input))
                        }
                        reader.readAsArrayBuffer(msg.data)
                    },
                    "onclose": () => this.onclose()
                });
                this._timer_qps = null
                this._timer = null
                this._timer_system = null
                this._authentication = null
                this._authing = true
                this._auth_info = ttb.createElement("h3").style("margin-right: 16px;").event('click', () => {
                    if (this._authing) return
                    ttb.getModal().open(
                        this._auth.clear().append(
                            ...(this._authentication ? this._auth_logout : this._auth_login)
                        )
                    ).thenClose((event) => {
                        this._auth_login[1].getChildrens()[0].getChildrens()[0].setValue('')
                        this._auth_login[1].getChildrens()[0].getChildrens()[1].setValue('')
                        ttb.getModal().close()
                    });
                })
                this.menus = []
                this._auth_login = [
                    ttb.createElement("div").append(
                        ttb.createElement("h3").setText("Login to dashboard"),
                    ),
                    ttb.createElement("div").style("margin-top: 8px; margin-bottom: 8px").class("auth").append(
                        ttb.createElement("form").setAttribute("onsubmit", "return false;").event("submit", (event) => {
                            const target = event.target
                            for (const child of target.children) {
                                if (child.type != "submit") {
                                    if (!child.value) {
                                        child.focus()
                                        return false;
                                    }
                                }
                            }
                            set_progress(0.7)
                            ttb.request({
                                "path": "./auth",
                                "headers": {
                                    "Authorization": `TTB ${window.btoa(JSON.stringify(this._getInputAuthInfo()))}`
                                },
                                "error": (xhr) => {
                                    if (xhr.status == 401) ttb.createNotication("error", "", ttb.createElement("h4").setText("账户密码"), ttb.createElement("p").setText("您的账户和密码输入错误"))
                                },
                                "success": (xhr) => {
                                    this._auth_login[1].getChildrens()[0].getChildrens()[0].setValue('')
                                    this._auth_login[1].getChildrens()[0].getChildrens()[1].setValue('')
                                    this._authentication = xhr.response
                                    this.setAuthInfo()
                                    ttb.createNotication("success", "", ttb.createElement("h4").setText("成功登入账户"), ttb.createElement("p").setText("欢迎回来, " + xhr.response))
                                    ttb.getModal().close()
                                }
                            }).finally(() => {
                                set_progress(1)
                            })
                            return false;
                        }).append(
                            ttb.createElement("input").setAttribute("placeholder", "用户").setAttribute("type", "text"),
                            ttb.createElement("input").setAttribute("placeholder", "密码").setAttribute("type", "password"),
                            ttb.createElement("input").setAttribute("type", "submit").setValue("登陆")
                        )
                    )
                ]
                this._auth_logout = [
                    ttb.createElement("div").append(
                        ttb.createElement("h3").setText("Logout the dashboard"),
                    ),
                    ttb.createElement("div").style("margin-top: 8px; margin-bottom: 8px").class("auth").append(
                        ttb.createElement("input").setAttribute("type", "submit").setValue("登出").event('click', () => {
                            document.cookie = `auth=;max-age=0`
                            this._authentication = null
                            this.setAuthInfo()
                            set_progress(1)
                            ttb.getModal().close()
                        })
                    )
                ]
                this._auth = ttb.createElement("div").class("panel").style("width: 800px", "min-height: 600px; margin-left: 16px; margin-right: 16px")
                header.append(this._auth_info)
            }
            _getInputAuthInfo() {
                const child = this._auth_login[1].getChildrens()[0].getChildrens()
                return {
                    "username": child[0].base.value,
                    "password": child[1].base.value
                }
            }
            onclose() {
                ttb.createNotication("warn", "", ttb.createElement("h4").setText("实时隧道已关闭"))
                dashboard.runtime = null
            }
            onopen() {
                ttb.createNotication("info", "", ttb.createElement("h4").setText("实时隧道已开启"))
                this.send("runtime")
                this.send("storage")
                this.send("status")
                this._timer_qps?.block();
                this._timer?.block()
                this._timer_system?.block()
                this._timer_qps = ttb.runTaskRepeat(() => {
                    this.send("qps")
                }, 0, 5000)
                this._timer = ttb.runTaskRepeat(() => {
                    this.send("dashboard")
                }, 0, 10000)
                this._timer_system = ttb.runTaskRepeat(() => {
                    this.send("system")
                }, 0, 1000)
            }
            send(type, data) {
                const buf = new DataOutputStream()
                buf.writeString(type)
                buf.write(this._serializeData(data))
                this.ws.send(buf)
            }
            setAuthInfo() {
                if (this._authing) {
                    this._auth_info.setStyle("cursor", "not-allowed")
                    this._auth_info.setText("获取账户信息中")
                    for (const m of this.menus) delete_menu(m.key)
                } else {
                    this._auth_info.setStyle("cursor", "pointer")
                    if (this._authentication) {
                        this._auth_info.setText(this._authentication)
                        for (const m of this.menus) menu(m.key, m.icon, m.text, m.core)
                    } else {
                        this._auth_info.setText("登陆")
                        for (const m of this.menus) delete_menu(m.key)
                    }
                }
            }
            menu(key, icon, text, core) {
                this.menus.push({
                    key, icon, text, core
                })
            }
            message(type, data) {
                if (type == "auth") {
                    this._authing = false
                    this._authentication = data
                    this.setAuthInfo()
                }
                if (type == "runtime") {
                    dashboard.runtime = data
                    dashboard.update()
                }
                if (type == "status") {
                    dashboard.updateStatus(data)
                }
                if (type == "dashboard") {
                    const hourly_data = data.hourly
                    const daily_data = data.days;
                    let min = Math.max(...hourly_data.map(v => v._hour))
                    let hits, bytes, io, cache;
                    {
                        io = Array.from({ length: min }, (_, __) => 0);
                        cache = Array.from({ length: min }, (_, __) => 0);
                        for (const val of hourly_data) {
                            io[val._hour] = val.hits
                            cache[val._hour] = val.cache_hits
                            min = Math.max(min, val._hour)
                        }
                        dashboard._e_hits.setOption({
                            legend: {
                                data: ["I/O访问数", "缓存访问数"]
                            },
                            yAxis: {
                                max: Math.max(10, ...io, ...cache),
                            },
                            series: [{
                                name: "I/O访问数",
                                data: io,
                                type: 'line',
                                smooth: true
                            }, {
                                name: "缓存访问数",
                                data: cache,
                                type: 'line',
                                smooth: true
                            }]
                        })
                        hits = ttb.sum(...io, ...cache)
                    }
                    {
                        io = Array.from({ length: min }, (_, __) => 0);
                        cache = Array.from({ length: min }, (_, __) => 0);
                        for (const val of hourly_data) {
                            io[val._hour] = val.bytes
                            cache[val._hour] = val.cache_bytes
                        }
                        dashboard._e_bytes.setOption({
                            tooltip: {
                                formatter: (params) => {
                                    return dashboard._e_templates(params, v => dashboard._format_bytes(v))
                                }
                            },
                            legend: {
                                data: ["I/O访问文件大小", "缓存访问文件大小"]
                            },
                            yAxis: {
                                max: Math.max(10, ...io, ...cache),
                                axisLabel: {
                                    formatter: (value) => {
                                        return dashboard._format_bytes(value)
                                    }
                                }
                            },
                            series: [{
                                name: "I/O访问文件大小",
                                data: io,
                                type: 'line',  
                                smooth: true
                            }, {
                                name: "缓存访问文件大小",
                                data: cache,
                                type: 'line',  
                                smooth: true
                            }]
                        })
                        bytes = ttb.sum(...io, ...cache)
                    }
                    dashboard._page[1].getChildrens()[0].getChildrens()[0].getChildrens()[0].getChildrens()[0].getChildrens()[1].setText(dashboard._format_number_unit(hits))
                    dashboard._page[1].getChildrens()[0].getChildrens()[0].getChildrens()[0].getChildrens()[1].getChildrens()[1].setText(dashboard._format_bytes(bytes))
                    {
                        io = Array.from({ length: 30 }, (_, __) => 0);
                        cache = Array.from({ length: 30 }, (_, __) => 0);
                        for (const val of daily_data) {
                            io[val._day] = val.hits
                            cache[val._day] = val.cache_hits
                        }
                        dashboard._e_daily_hits.setOption({
                            legend: {
                                data: ["I/O访问数", "缓存访问数"]
                            },
                            yAxis: {
                                max: Math.max(10, ...io, ...cache),
                            },
                            series: [{
                                name: "I/O访问数",
                                data: io,
                                type: 'line',  
                                smooth: true
                            }, {
                                name: "缓存访问数",
                                data: cache,
                                type: 'line',  
                                smooth: true
                            }]
                        })
                        hits = ttb.sum(...io, ...cache)
                    }
                    {
                        const io = Array.from({ length: 30 }, (_, __) => 0);
                        const cache = Array.from({ length: 30 }, (_, __) => 0);
                        for (const val of daily_data) {
                            io[val._day] = val.bytes
                            cache[val._day] = val.cache_bytes
                        }
                        dashboard._e_daily_bytes.setOption({
                            tooltip: {
                                formatter: (params) => {
                                    return dashboard._e_templates(params, v => dashboard._format_bytes(v))
                                }
                            },
                            legend: {
                                data: ["I/O访问文件大小", "缓存访问文件大小"]
                            },
                            yAxis: {
                                max: Math.max(10, ...io, ...cache),
                                axisLabel: {
                                    formatter: (value) => {
                                        return dashboard._format_bytes(value)
                                    }
                                }
                            },
                            series: [{
                                name: "I/O访问文件大小",
                                data: io,
                                type: 'line',  
                                smooth: true
                            }, {
                                name: "缓存访问文件大小",
                                data: cache,
                                type: 'line',  
                                smooth: true
                            }]
                        })
                        bytes = ttb.sum(...io, ...cache)
                    }
                    dashboard._page[1].getChildrens()[0].getChildrens()[0].getChildrens()[0].getChildrens()[2].getChildrens()[1].setText(dashboard._format_number_unit(hits))
                    dashboard._page[1].getChildrens()[0].getChildrens()[0].getChildrens()[0].getChildrens()[3].getChildrens()[1].setText(dashboard._format_bytes(bytes))
                }
                if (type == "system") {
                    dashboard._page[1].getChildrens()[0].getChildrens()[1].getChildrens()[0].getChildrens()[0].getChildrens()[1].setText(dashboard._format_number_unit(data.connections))
                    dashboard._page[1].getChildrens()[0].getChildrens()[1].getChildrens()[0].getChildrens()[1].getChildrens()[1].setText(dashboard._format_bytes(data.memory))
                    dashboard._page[1].getChildrens()[0].getChildrens()[1].getChildrens()[0].getChildrens()[2].getChildrens()[1].setText(`${dashboard._format_number_unit(data.cache.total)}(${dashboard._format_bytes(data.cache.bytes)})`)
                    dashboard._page[1].getChildrens()[0].getChildrens()[1].getChildrens()[0].getChildrens()[3].getChildrens()[1].setText(data.cpu.toFixed(2) + "%")
                }
                if (type == "qps") {
                    const time = parseInt(ttb.getTimestamp() / 1000)
                    const ntime = (time % 5 != 0 ? 5 : 0) - (time % 5) + time
                    const ltime = ntime - 300;
                    const qps = []
                    var sums = [];
                    var date = []
                    for (let i = ltime; i <= ntime; i++) {
                        let value = (!data.hasOwnProperty(i) ? 0 : data[i]);
                        sums.push(value);
                        if (i % 5 == 0) {
                            qps.push({value: ttb.sum(...sums) / sums.length, raw: sums});
                            sums = []
                            date.push(dashboard._e_format_time(i * 1000))
                        }
                    }
                    dashboard._page[1].getChildrens()[1].getChildrens()[0].getChildrens()[0].getChildrens()[0].setText(dashboard._format_number_unit(ttb.sum(...ttb.collectionSingleList(qps.map(v => [...v.raw])))))
                    dashboard._e_qps.setOption({
                        xAxis: {
                            data: date
                        },
                        series: [{data: qps}]
                    })

                }
                root_handler("_ws_message", type, data)
            }
            _deserializeData(input) {
                const type = input.readVarInt()
                switch (type) {
                    case 0: // string
                        return input.readString()
                    case 1: // bool
                        return input.readBoolean()
                    case 2: // float
                        return parseFloat(input.readString())
                    case 3: // bool
                        return parseInt(input.readString())
                    case 4: {// list
                        const length = input.readVarInt()
                        const data = []
                        for (let _ = 0; _ < length; _++) data.push(this._deserializeData(input))
                        return data
                    }
                    case 5: {// table
                        const length = input.readVarInt()
                        const data = {}
                        for (let _ = 0; _ < length; _++) {
                            data[this._deserializeData(input)] = this._deserializeData(input)
                        }
                        return data
                    }
                    case 6:
                        return null
                    default:
                        console.log(type)
                        return null
                }
            }
            _serializeData(data) {
                const buf = new DataOutputStream()
                switch (typeof data) {
                    case "string": {
                        buf.writeVarInt(0)
                        buf.writeString(data)
                        break;
                    }
                    case "boolean": {
                        buf.writeVarInt(1)
                        buf.writeBoolean(data)
                        break;
                    }
                    case "number": {
                        if (Number.isInteger(data)) {
                            buf.writeVarInt(3)
                            buf.writeString(data.toString())
                        }
                        break;
                    }
                    case "object": {
                        if (Array.isArray(data)) {
                            buf.writeVarInt(4)
                            buf.writeVarInt(data.length)
                            for (v of data) {
                                buf.write(this._serializeData(v))
                            }
                        } else if (data != null) {
                            buf.writeVarInt(5);
                            buf.writeVarInt(Object.keys(data).length);
                            for (const key in data) {  
                                buf.write(this._serializeData(key)); 
                                buf.write(this._serializeData(data[key]));
                            }  
                        } else if (data == null) {
                            buf.writeVarInt(6);
                        }
                        break;
                    }
                    case "undefined": {
                        buf.writeVarInt(6); 
                        break;
                    }
                    default:
                        buf.writeVarInt(6); 
                        console.log(data)
                }
                return buf
            }
        }
        class Measure {

        }
        const ws = new MainWebSocket()
        const dashboard = new Dashboard()
        const measure = new Measure()
        menu("dashboard", "", "数据统计", dashboard)
        ws.menu("measure", "", "带宽测试", measure)
        ws.setAuthInfo()
    })();

    display_left()
    ttb.set_styles(global_styles)
    popstate()
    resize()
    ttb.init()
    ttb.setResponseHandler({
        "error": (e) => {
            console.log(e)
            ttb.createNotication("error", "", ttb.createElement("h4").setText("请求远程数据错误"), ttb.createElement("p").setText("返回代码为：" + e.status))
        }
    })
})()