const UNIT_BYTES = [
    "", "K", "M", "G", "T", "E"
];
const calc_bits = (v) => {
    v *= 8
    unit = UNIT_BYTES[0]
    for (units of UNIT_BYTES) {
        if (Math.abs(v) >= 1024.0) {
            v /= 1024.0
            unit = units
        }
    }
    return `${v.toFixed(2)} ${unit}`
}
const calc_bytes = (v) => {
    unit = UNIT_BYTES[0]
    for (units of UNIT_BYTES) {
        if (Math.abs(v) >= 1024.0) {
            v /= 1024.0
            unit = units
        }
    }
    return `${v.toFixed(2)} ${unit}`
}
const calc_more_bytes = (...values) => {
    v = Math.max(...values)
    unit = UNIT_BYTES[0]
    i = 0
    for (units of UNIT_BYTES) {
        if (Math.abs(v) >= 1024.0) {
            v /= 1024.0
            unit = units
            i += 1
        }
    }
    return [values.map(v => v / 1024 ** i), unit]
}

(() => {
    const default_styles = {
        "body":"background-color: rgb(247, 248, 250);",
        ".container .button":"display: inline-flex;-webkit-box-align: center;align-items: center;-webkit-box-pack: center;justify-content: center;box-sizing: border-box;-webkit-tap-highlight-color: transparent;background-color: transparent;outline: 0px;border: 0px;margin: 0px;border-radius: 5px;cursor: pointer;user-select: none;vertical-align: middle;appearance: none;text-decoration: none;font-family: inherit;font-weight: 500;line-height: 1.25;text-transform: uppercase;max-width: 360px;position: relative;flex-shrink: 0;overflow: hidden;white-space: normal;text-align: center;flex-direction: column;color: rgba(0, 0, 0, 0.7);z-index: 1;padding: 4px 12px;min-height: 0px;min-width: 0px;font-size: 12px;transition: background-color 0.3s ease, color 0.3s ease;",
        ".container .button.selected":"background-color: rgb(15, 198, 194); color: white;",
        ".container .button.force:hover":"background-color: #ADD8E6; color: white;",
        ".container .button.force:active":"background-color: rgb(15, 198, 194);",
        ".container":"display: flex;",
        ".container .right":"margin: 8px;min-width: calc(100vw - 232px);margin-left: 216px;margin-top: 56px;padding-top: 16px;",
        ".container .left":"position: fixed;min-width: 200px;max-width: 200px;min-height: 100vh;box-shadow: rgba(145, 158, 171, 0.2) 0px 4px 10px;backdrop-filter: blur(5px);z-index: 2;margin-top: 64px;padding-top: 16px;",
        ".container .left .list":"overflow-y: auto;min-height: 80px;",
        ".header-bar":"background-color: rgb(247, 248, 250);box-shadow: 0px 4px 10px rgba(145, 158, 171, 0.2);z-index: 5;position: fixed;min-width: 100vw;max-height: 56px;min-height: 40px;padding: 8px;padding-left: 16px;padding-right: 16px;align-items: center;",
        ".container .left .domain":"text-align: center;padding-top: 8px;padding-bottom: 8px;",
        ".container .left button":"margin: 0;margin-left: 10px;margin-top: 4px;margin-bottom: 4px;transition: color 200ms linear 0s, color 200ms linear 0s;border-radius: 8px;border: 0;background-color: transparent;list-style-type: none;text-align: left;cursor: pointer;width: 176px;height: 100%;font-size: medium;padding: 8px;",
        ".container .left .sidebutton":"color: rgba(0, 0, 0, 0.5);width: 150px;margin-left: 16px;display: flex;align-items: center;",
        ".container .left .sidebutton:hover":"color: #8dcffc;",
        ".container .left .sidebutton:hover .cycle":"background-color: #8dcffc;transition: background-color 200ms linear 0s;",
        ".container .left .sidebutton.selected":"background-color: transparent;color: black;font-weight: bold;box-shadow: none;",
        ".container .left .sidebutton.selected .cycle":"width: 8px;height: 8px;background-color: #0FC6C2;transition: background-color 200ms linear 0s;margin-left: 0px;margin-right: 0px;",
        ".container .left button:hover":"color: #0FC6C2;transition: color 200ms linear 0s;text-decoration: none;",
        ".container .left button.selected":"background-color: #0FC6C2;color: #fff;box-shadow: rgba(15, 198, 194, 0.2) 0px 10px 25px 0px;",
        ".container .left .sidebutton .cycle":"width: 4px;height: 4px;background-color: rgba(0, 0, 0, 0.4);transition: background-color 200ms linear 0s;border-radius: 50%;margin-left: 2px;margin-right: 2px;",
        ".container .left .sidebutton span":"margin-left: 8px;",
        ".container .right .panel":"background-color: rgb(255, 255, 255);color: rgb(0, 0, 0);transition: box-shadow 300ms cubic-bezier(0.4, 0, 0.2, 1) 0ms;border-radius: 4px;background-image: none;padding: 24px;box-shadow: rgba(145, 158, 171, 0.2) 0px 4px 10px;margin: 16px;",
        ".container .title":"margin: 0px 0px 6px;font-family: inherit;font-weight: 400;line-height: 1.5;color: rgba(0, 0, 0, 0.5);font-size: 14px;",
        ".container .value":"margin: 0px;font-family: inherit;font-weight: 400;line-height: 1.5;color: rgba(0, 0, 0, 0.7);font-size: 24px;",
        ".container .value.warn":"color: rgb(255, 191, 0);",
        ".container .geo-change":"overflow: hidden;display: flex;padding: 5px;border: 1px solid rgb(227, 232, 239);min-height: 24px;height: 24px;background-color: rgb(255, 255, 255);border-radius: 4px;",
        ".container .qsaw":"display: flex;flex-flow: wrap;flex-basis: 75%;",
        ".container .qsar":"flex-basis: 25%;",
        ".container .qsari":"width: 100%;margin-top: 16px;",
        ".container .qsari .text p":"margin: 0px;font-family: inherit;font-weight: 400;line-height: 1.5;color: rgba(0, 0, 0, 0.7);font-size: 14px;",
        ".container .qsari .text":"display: flex;justify-content: space-between;width: 100%;",
        ".container .qsari .rank":"width: 50%;background-color: rgb(15, 198, 194);border-radius: 2px;height: 4px;",
        ".container .qsari .rank_unfull":"width: 100%;margin-top: 8px;background-color: rgb(227, 232, 239);border-radius: 2px;height: 4px;",
        ".container-center":"display: flex;justify-content: center;flex-wrap: nowrap;flex-direction: column;align-items: center;",
        ".container .vcmp-status-bar":"border-radius: 8px;background-color: rgba(0, 0, 0, 0.075);width: 128px;height: 32px;margin: 8px;display: flex;justify-content: center;align-items: center;transition: color 200ms linear 0s, color 200ms linear 0s;border: 0;cursor: pointer;",
        ".container .vcmp-status-bar p":"font-size: medium;margin-left: 10px;",
        ".container .vcmp-status-bar:hover":"color: #8dcffc;",
        ".container .vcmp-status-online":"width: 12px;height: 12px;border-radius: 50%;background-color: #0FC6C2;margin: 8px;",
        ".container .vcmp-status-offline":"width: 12px;height: 12px;border-radius: 50%;background-color: rgba(0, 0, 0, 0.5);margin: 8px;margin-right: 0;",
    }
    set_styles(default_styles)
    Extendi18nSets("zh_cn", {
        "list.dashboard": "数据统计",
        "list.clusters": "节点",
        "list.clusters.rank": "排名榜",
        "list.clusters.myself": "本地节点",
        "list.master": "主控统计"
    })
    const buttons = {
        "dashboard": Extendi18n("list.dashboard"),
        "master": Extendi18n("list.master"),
        "clusters": [
            Extendi18n("list.clusters"),
            ["rank", Extendi18n("list.clusters.rank")],
            ["self", Extendi18n("list.clusters.myself")]
        ]
    }
    const time_hours = Array.from({length: 24}, (_, i) => i + " 时")
    const core_modules = {
        "master": {
            "connect": () => {
                if (!("master" in core_modules_locals)) {
                    core_modules_locals["master"] = {
                        "nodes":        echarts.init(document.getElementById("e-clusters-nodes")),
                        "bandwidth":    echarts.init(document.getElementById("e-clusters-bandwidth")),
                        "bytes":        echarts.init(document.getElementById("e-clusters-bytes")),
                        "req":          echarts.init(document.getElementById("e-clusters-req")),
                        "load":         echarts.init(document.getElementById("e-master-cpu")),
                        "options": {tooltip:{trigger:"axis",axisPointer:{type:"cross",label:{backgroundColor:"#0FC6C2"}}},grid:{left:"3%",right:"4%",bottom:"3%",containLabel:!0},xAxis:{type:"category",boundaryGap:!1,data:time_hours},yAxis:{type:"value",axisLabel:{formatter:"{value}"}},series:[{name:"",type:"line",stack:"",areaStyle:{},color:"#0FC6C2",symbol:"circle",symbolSize:4,data:[],smooth:!0,animationEasing:"cubicOut",animationDelay:function(t){return 10*t}}]},
                        "refresh": () => {
                            axios.get("master?url=/openbmclapi/metric/dashboard").then(response => {
                                if (response.status != 200) return
                                data = response.data
                                console.log(data)
                                document.getElementById("t-clusters-nodes").innerText = data.currentNodes
                                document.getElementById("t-clusters-bandwidth").innerText = data.currentBandwidth.toFixed(2) + " M"
                                document.getElementById("t-clusters-bytes").innerText = calc_bytes(data.bytes * 1024.0)
                                document.getElementById("t-clusters-req").innerText = (data.hits / 10000).toFixed(2)
                                nodes = []
                                bytes = []
                                unit_bytes = UNIT_BYTES[0]
                                hits = []
                                bandwidth = []
                                for (const obj of data.hourly) {
                                    nodes.push(obj.nodes)
                                    bytes.push((obj.bytes / 1024.0 ** 3).toFixed(2))
                                    hits.push((obj.hits / 10000).toFixed(2))
                                    bandwidth.push((obj.bandwidth * 8 / 1024.0 ** 2).toFixed(2))
                                }
                                core_modules_locals["master"]["nodes"]      .setOption({tooltip:{formatter: e =>'<div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:#0fc6c2;"></span><span style="font-size:14px;color:#666;font-weight:400;margin-left:2px">节点在线:  </span><span style="float:right;margin-left:20px;font-size:14px;color:#666;font-weight:900">'+e[0].data+'个</span><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div>'},series: [{data: nodes}]})
                                core_modules_locals["master"]["bytes"]      .setOption({tooltip:{formatter: e =>'<div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:#0fc6c2;"></span><span style="font-size:14px;color:#666;font-weight:400;margin-left:2px">流量:      </span><span style="float:right;margin-left:20px;font-size:14px;color:#666;font-weight:900">'+e[0].data+'TiB</span><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div>'},series: [{data: bytes}]})
                                core_modules_locals["master"]["req"]        .setOption({tooltip:{formatter: e =>'<div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:#0fc6c2;"></span><span style="font-size:14px;color:#666;font-weight:400;margin-left:2px">请求：     </span><span style="float:right;margin-left:20px;font-size:14px;color:#666;font-weight:900">'+e[0].data+'万</span><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div>'},series: [{data: hits}]})
                                core_modules_locals["master"]["bandwidth"]  .setOption({tooltip:{formatter: e =>'<div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><div style="margin: 0px 0 0;line-height:1;"><span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:#0fc6c2;"></span><span style="font-size:14px;color:#666;font-weight:400;margin-left:2px">带宽：     </span><span style="float:right;margin-left:20px;font-size:14px;color:#666;font-weight:900">'+e[0].data+'Mbps</span><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div><div style="clear:both"></div></div>'},series: [{data: bandwidth}]})
                                core_modules_locals["master"]["load"]       .setOption({series:[{type:"gauge",center:["50%","50%"],radius:"55%",min:0,max:100,axisLine:{lineStyle:{width:10,color:[[.3,"#2CE69B"],[.5,"#42AAFF"],[.7,"#F1BF4B"],[1,"#FF708D"]]}},pointer:{width:5},data:[{value:(100*data.load).toFixed(2)}]}]});
                            })
                        }
                    }
                    core_modules_locals["master"]["nodes"]      .setOption(core_modules_locals["master"]["options"])
                    core_modules_locals["master"]["bandwidth"]  .setOption(core_modules_locals["master"]["options"])
                    core_modules_locals["master"]["bytes"]      .setOption(core_modules_locals["master"]["options"])
                    core_modules_locals["master"]["req"]        .setOption(core_modules_locals["master"]["options"])
                    core_modules_locals["master"].refresh()
                    setInterval(core_modules_locals["master"].refresh, 300)
                }
            },
            "resize": () => {
                core_modules_locals["master"]["nodes"]      .resize()
                core_modules_locals["master"]["bandwidth"]  .resize()
                core_modules_locals["master"]["bytes"]      .resize()
                core_modules_locals["master"]["req"]        .resize()
                core_modules_locals["master"]["load"]       .resize()
            },
            "page": () => {
                return [
                    ExtendFlex().append(
                        ExtendElement("div").append(
                            ExtendElement("div").css("panel").append(
                                ExtendElement("h4").text("当前节点在线").valueOf(),
                                ExtendElement("h2").append(
                                    ExtendElement("span").text("0").id("t-clusters-nodes").valueOf(),
                                    ExtendElement("span").text("个").valueOf()
                                ).valueOf(),
                                ExtendElement("div").id("e-clusters-nodes").style("height: 216px; width: 100%").valueOf()
                            ).valueOf(),
                            ExtendElement("div").css("panel").append(
                                ExtendElement("h4").text("当日全网总流量").valueOf(),
                                ExtendElement("h2").append(
                                    ExtendElement("span").text("0 ").id("t-clusters-bytes").valueOf(),
                                    ExtendElement("span").text("iB").valueOf()
                                ).valueOf(),
                                ExtendElement("div").id("e-clusters-bytes").style("height: 216px; width: 100%").valueOf()
                            ).valueOf(),
                        ),
                        ExtendElement("div").append(
                            ExtendElement("div").css("panel").append(
                                ExtendElement("h4").text("当前出网带宽").valueOf(),
                                ExtendElement("h2").append(
                                    ExtendElement("span").text("0 ").id("t-clusters-bandwidth").valueOf(),
                                    ExtendElement("span").text("bps").valueOf()
                                ).valueOf(),
                                ExtendElement("div").id("e-clusters-bandwidth").style("height: 216px; width: 100%").valueOf()
                            ).valueOf(),
                            ExtendElement("div").css("panel").append(
                                ExtendElement("h4").text("当日全网总请求数").valueOf(),
                                ExtendElement("h2").append(
                                    ExtendElement("span").text("0").id("t-clusters-req").valueOf(),
                                    ExtendElement("span").text("万").valueOf()
                                ).valueOf(),
                                ExtendElement("div").id("e-clusters-req").style("height: 216px; width: 100%").valueOf()
                            ).valueOf(),
                        ),
                        ExtendElement("div").css("panel").append(
                            ExtendElement("h4").text("五分钟负载").valueOf(),
                            ExtendElement("div").id("e-master-cpu").style("height: 98%; width: 100%").valueOf()
                        ),
                    ).childWidth("33.33%", "33.33%", "33.33%").valueOf()
                ]
            }
        }
    }
    const handler = ((root, key, type) => {
        root += (key ? "-" + key : "")
        if (last_root != root) {
            if (last_root in core_modules && "disconnect" in core_modules[last_root]) {
                try {
                    core_modules[last_root]["disconnect"]()
                } catch (e) {
                    console.log(e)
                }
            }
            while (document.getElementsByClassName("right")[0].firstChild != null) document.getElementsByClassName("right")[0].removeChild(document.getElementsByClassName("right")[0].firstChild)
            last_root = root
        }
        if (!(root in core_modules) || !(type in core_modules[root])) return
        try {
            page = null
            if (type == "connect" && "page" in core_modules[root]) page = core_modules[root]["page"]()
            if (page != null) document.getElementsByClassName("right")[0].append(ExtendElement("div").id("module-" + root).append(...(Array.isArray(page) ? page : [page])).valueOf())
            core_modules[root][type]()
        } catch (e) {
            console.log(e)
        }
    });
    const core_modules_locals = {
    }
    const popstate = () => {
        const key = getURLKey() ? getURLKey() : Object.keys(buttons)[0]
        const last_key_sub = last_key_b
        last_key_b = ''
        for (const bkey in buttons) {
            if (last_key != key) {
                if (bkey == key) document.getElementById("list-" + bkey).classList.add("selected")
                else document.getElementById("list-" + bkey).classList.remove("selected")
            }
            if (document.getElementById("list-sub-" + bkey)) {
                if (bkey == key) document.getElementById("list-sub-" + bkey).style.display = "block"
                else document.getElementById("list-sub-" + bkey).style.display = "none"
                const skey = getURLKeyParams()['key'] ? getURLKeyParams()['key'] : Object.keys(buttons[bkey])[1]
                if (skey != last_key_sub) {
                    for (const subkey of buttons[bkey].slice(1)) {
                        if (subkey[0] == skey) {
                            document.getElementById("list-sub-" + bkey + "-" + subkey[0]).classList.add("selected")
                            last_key_b = skey
                        } else document.getElementById("list-sub-" + bkey + "-" + subkey[0]).classList.remove("selected")
                    }
                }
            }
        }
        if (last_key != key || (last_key_b && last_key_b != last_key_sub)) {
            if (last_key && (last_key_b && last_key_b == last_key_sub)) handler(last_key, last_key_sub, "disconnect")
            handler(key, last_key_b, "connect")
        }
        last_key = key;
    }
    let last_key = '';
    let last_key_b = '';
    let last_root = '';
    (() => {
        document.body.prepend(
            ExtendFlex().append(
                ExtendFlex().css("domain", "extend-flex-auto").append(
                    ExtendElement("span").append(
                        ExtendElement("h2").text("Python OpenBMCLAPI Dashboard").valueOf(),
                        ExtendElement("span").text("Powered by ").append(
                            ExtendElement("a").text("TTB Network").setAttr("href", "https://github.com/TTB-Network/python-openbmclapi/").valueOf()
                        ).id("dashboard-geo").valueOf()
                    ).valueOf(),
                ).valueOf(),
            ).css("header-bar").valueOf(),
            ExtendElement("div").css("container").append(
                ExtendElement("div").css("left").append(
                    ExtendElement("div").css("list").valueOf()
                ).valueOf(),
                ExtendElement("div").css("right").valueOf()
            ).valueOf()
        );
        for (const key in buttons) {
            const value = buttons[key]
            element = ExtendElement("button").event("click", () => {
                window.location.hash = key + (typeof value != "string" ? "?key=" + value[1][0] : "")
            }).id("list-" + key)
            sub = null;
            if (typeof value == "string") element.text(value)
            else {
                element.text(value[0])
                sub = ExtendElement("div").style("display: none").id("list-sub-" + key)
                value.slice(1).forEach(v => sub.append(ExtendElement("button").append(ExtendElement("div").css("cycle").valueOf(), ExtendElement("span").text(v[1]).valueOf()).id("list-sub-" + key + "-" + v[0]).css("sidebutton").event('click', () => {
                    window.location.hash = key + (typeof value != "string" ? "?key=" + v[0] : "")
                }).valueOf()));
            }
            document.getElementsByClassName("list")[0].append(element.valueOf())
            if (sub) document.getElementsByClassName("list")[0].append(sub.valueOf())
        }
        
        // modules
        Object.values(core_modules).filter(v => "init" in v).forEach(v => v["init"]())

    })();
    popstate()
    window.addEventListener("popstate", popstate)
    window.addEventListener('resize', () => {
        if (last_root in core_modules && "resize" in core_modules[last_root]) core_modules[last_root]["resize"]()
    })
})()