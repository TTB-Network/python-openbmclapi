const extend_default_styles = {
    "body,ol,ul,h1,h2,h3,h4,h5,h6,p,th,td,dl,dd,form,fieldset,legend,input,textarea,select": "margin:0;padding:0",
    "body": "font:12px;background:#fff;-webkit-text-size-adjust:100%",
    "a": "color:#172c45;text-decoration:none",
    "a:hover": "color:#cd0200;text-decoration:underline",
    "em": "font-style:normal",
    "li": "list-style:none",
    "img": "border:0;vertical-align:middle",
    "table": "border-collapse:collapse;border-spacing:0",
    "p": "word-wrap:break-word",
    "#extend-notifications div": "position: fixed;bottom: 12vh;right: 0;float: right;width: auto;background-color: rgba(255, 255, 255, 0.8);border: 1px solid #ccc;border-radius: 5px 0 0 5px;padding: 0.5vw;box-sizing: border-box;transform: translateX(100%);transition: transform 0.3s, bottom 0.3s;font-size: 0.75vw;",
    "#extend-notifications": "position: fixed;right: 0;float: right;width: auto;",
    "#extend-notifications div.show": "transform: translateX(0);",
    "#extend-alerts div": "position: fixed;top: 2vh; width: auto;height: 2.25vw;background-color: rgba(255, 255, 255, 0.8);border: 1px solid #ccc;border-radius: 5px;padding: 0.5vw;box-sizing: border-box;font-size: 0.75vw;white-space: nowrap;",
    "#extend-alerts div.show": "transform: translate(-50%, 0);",
    ".extend-panel-container": "position: absolute;z-index: 10;display: flex;justify-content: center;align-items: center;width: 100%;height: 100%;background-color: rgba(0, 0, 0, 0.8);left: 0;top: 0;float: left;opacity: 1;transition: opacity 225ms cubic-bezier(0.4, 0, 0.2, 1) 0ms;",
    ".extend-panel-container .panel": "max-width: 800px;width: 800px;height: 100%;display: flex;justify-content: center;align-items: center;",
    ".extend-panel-container.close": "opacity: 0;z-index: -1;",
    ".extend-panel-container .panel .paper": "border-radius: 12px;width: 800px;max-width: 800px;color: rgb(0, 0, 0);transition: box-shadow 300ms cubic-bezier(0.4, 0, 0.2, 1) 0ms;border-radius: 4px;box-shadow: rgba(0, 0, 0, 0.2) 0px 11px 15px -7px, rgba(0, 0, 0, 0.12) 0px 24px 38px 3px, rgba(0, 0, 0, 0.12) 0px 9px 46px 8px;background-color: rgb(255, 255, 255);background-image: none;margin: 32px;position: relative;overflow-y: auto;display: flex;flex-direction: column;max-height: calc(100% - 64px);",
    ".extend-panel-container .panel .header": "margin: 0px;font-family: inherit;line-height: 1.6;flex: 0 0 auto;font-weight: 600;font-size: 16px;padding: 32px 32px 16px;display: flex;-webkit-box-pack: justify;justify-content: space-between;-webkit-box-align: center;align-items: center;",
    ".extend-panel-container .panel .body": "flex: 1 1 auto;overflow-y: auto;padding-top: 0px;padding: 20px 24px;",
    ".extend-panel-container .panel .footer": "display: flex;-webkit-box-align: center;align-items: center;-webkit-box-pack: end;justify-content: flex-end;flex: 0 0 auto;padding: 0px 32px 32px;",
    ".extend-panel-container .panel button.cancel": "padding-left: 30px;padding-right: 30px;display: inline-flex;-webkit-box-align: center;align-items: center;-webkit-box-pack: center;justify-content: center;position: relative;box-sizing: border-box;-webkit-tap-highlight-color: transparent;background-color: transparent;outline: 0px;border: 0px;margin: 0px;cursor: pointer;user-select: none;vertical-align: middle;appearance: none;text-decoration: none;font-family: inherit;font-weight: 500;font-size: 0.875rem;line-height: 1.75;text-transform: uppercase;min-width: 64px;padding: 6px 8px;border-radius: 4px;transition: background-color 250ms cubic-bezier(0.4, 0, 0.2, 1) 0ms, box-shadow 250ms cubic-bezier(0.4, 0, 0.2, 1) 0ms, border-color 250ms cubic-bezier(0.4, 0, 0.2, 1) 0ms, color 250ms cubic-bezier(0.4, 0, 0.2, 1) 0ms;color: rgb(15, 198, 194);box-shadow: none;",
    ".extend-panel-container .panel button.confirm": "margin-left: 8px;",
    ".extend-panel-container .panel button.close": "display: inline-flex;-webkit-box-align: center;align-items: center;-webkit-box-pack: center;justify-content: center;position: relative;box-sizing: border-box;-webkit-tap-highlight-color: transparent;background-color: transparent;outline: 0px;border: 0px;margin: 0px;cursor: pointer;user-select: none;vertical-align: middle;appearance: none;text-decoration: none;text-align: center;flex: 0 0 auto;font-size: 1.5rem;padding: 8px;border-radius: 50%;overflow: visible;transition: background-color 150ms cubic-bezier(0.4, 0, 0.2, 1) 0ms;color: rgba(0, 0, 0, 0.5);",
    ".extend-panel-container .panel button.close:hover": "background-color: rgba(0, 0, 0, 0.04);",
    ".extend-panel-container .panel button.close .svg": "user-select: none;width: 1em;height: 1em;display: inline-block;fill: currentcolor;flex-shrink: 0;transition: fill 200ms cubic-bezier(0.4, 0, 0.2, 1) 0ms;font-size: 20px;",
    ".extend-table .header": "display: flex;flex-wrap: nowrap",
    ".extend-flex": "display: flex;",
    ".extend-flex-out": "flex-wrap: wrap;",
    ".extend-flex-auto": "align-items: center;",
    ".extend-flex-space-between": "justify-content: space-between;",
    ".extend-checkbox.checked": "background-color: rgb(15, 198, 194);",
    ".extend-checkbox.checked:before": "transform: translate(calc(100% - 2px), 3px);",
    ".extend-checkbox:before": "content: '';position: absolute;width: 24px;height: 24px;background: white;transform: translate(3px, 3px);border-radius: 50%;transition: transform cubic-bezier(0.3, 1.5, 0.7, 1) 0.3s, background-color cubic-bezier(0.3, 1.5, 0.7, 1) 0.3s;",
    ".extend-checkbox": "appearance: none;width: 50px;height: 30px;position: relative;border-radius: 16px;cursor: pointer;background-color: #E9ECEE;",
    ".extend-input": "display: inline-flex;flex-direction: column;position: relative;margin: 16px 0px 8px;vertical-align: top;width: 140px;",
    ".extend-input.active label": "max-width: calc(133% - 32px);transform: translate(14px, -9px) scale(0.75);user-select: none;",
    ".extend-input label": "color: rgba(0, 0, 0, 0.7);font-size: 14px;font-family: inherit;font-weight: 400;line-height: 1.4375em;transform-origin: left top;white-space: nowrap;overflow: hidden;text-overflow: ellipsis;max-width: calc(100% - 24px);position: absolute;transform: translate(14px, 9px) scale(1);transition: color 200ms cubic-bezier(0, 0, 0.2, 1) 0ms, transform 200ms cubic-bezier(0, 0, 0.2, 1) 0ms, max-width 200ms cubic-bezier(0, 0, 0.2, 1) 0ms;z-index: 1;pointer-events: none;",
    ".extend-input .input-unit": "font-size: 14px;font-family: inherit;font-weight: 400;line-height: 1.4375em;box-sizing: border-box;cursor: text;display: inline-flex;-webkit-box-align: center;align-items: center;position: relative;border-radius: 4px;padding-right: 14px;",
    ".extend-input .input": "font-size: 14px;font-family: inherit;font-weight: 400;line-height: 1.4375em;box-sizing: border-box;cursor: text;-webkit-box-align: center;align-items: center;position: relative;border-radius: 4px;padding-right: 14px;",
    ".extend-input input": "font: inherit;letter-spacing: inherit;color: currentcolor;border: 0px;outline: none;box-sizing: content-box;background: none;height: 1.4375em;margin: 0px;-webkit-tap-highlight-color: transparent;width: 100%;padding: 8.5px 0px 8.5px 14px;",
    ".extend-input .input-full": "font: inherit;letter-spacing: inherit;color: currentcolor;border: 0px;outline: none;box-sizing: content-box;background: none;height: 1.4375em;margin: 0px;-webkit-tap-highlight-color: transparent;width: 100%;padding: 8.5px 0px 8.5px 14px;",
    ".extend-input .tips": "display: flex;height: 0.01em;max-height: 2em;-webkit-box-align: center;align-items: center;white-space: nowrap;color: rgba(0, 0, 0, 0.54);margin-left: 8px;",
    ".extend-input .tips p": "margin: 0px;font-size: 14px;font-family: inherit;font-weight: 400;line-height: 1.5;color: rgba(0, 0, 0, 0.7);",
    ".extend-input.active fieldset": "border-color: rgb(227, 232, 239);",
    ".extend-input fieldset": "text-align: left;position: absolute;inset: -5px 0px 0px;margin: 0px;padding: 0px 8px;pointer-events: none;border-radius: inherit;border-style: solid;border-width: 1px;overflow: hidden;border-color: rgba(0, 0, 0, 0.23);",
    ".extend-input fieldset legend": "float: unset;width: auto;overflow: hidden;padding: 0px;height: 11px;font-size: 0.75em;visibility: hidden;max-width: 0.01px;transition: max-width 50ms cubic-bezier(0, 0, 0.2, 1) 0ms;white-space: nowrap;",
    ".extend-input.active fieldset legend": "font-size: 0.75em;visibility: visible;white-space: nowrap;",
    ".extend-input .must": "color: rgb(255, 24, 68);",
};

class ExtendElements {
    constructor(type) {
        this.parent = document.createElement(type)
    }
    css(...args) {
        this.parent.classList.add(...args)
        return this;
    }
    rcss(...args) {
        this.parent.classList.remove(...args)
        return this;
    }
    append(...args) {
        this.parent.append(...args)
        return this
    }
    valueOf() {
        return this.parent;
    }
    text(text) {
        this.parent.innerText = text
        return this;
    }
    value(text) {
        this.parent.value = text
        return this;
    }
    html(html) {
        this.parent.innerHTML = html
        return this;
    }
    style(style) {
        this.parent.style = style;
        return this;
    }
    moreStyle(key, value) {
        this.parent.style[key] = value
        return this
    }
    event(event, handler) {
        this.parent.addEventListener(event, handler)
        return this
    }
    id(id) {
        this.parent.id = id;
        return this;
    }
    clear() {
        while (this.parent.firstChild != null) this.parent.removeChild(this.parent.firstChild) 
    }
    toString() {
        return this.valueOf()
    }
    setAttr(key, value) {
        this.parent.setAttribute(key, value)
        return this
    }
    static [Symbol.hasInstance](x) {
        return Object.getPrototypeOf(x) == ExtendElements.prototype
    }
}
const ExtendElement = (type) => {
    return new ExtendElements(type);
}
class ReconnectingWebSocket {
    constructor(url, handlers = {}) {
        this.url = "ws://" + url;
        this.ws = null;
        this.reconnectInterval = 1000;  // 重连间隔为1秒
        this.messageQueue = [];  // 用于缓存消息的队列
        this.handlers = handlers;  // 处理函数的对象
        this.stats = {
            sent: { count: 0, length: 0 },
            received: { count: 0, length: 0 }
        };
        this.connect()
        this.reconnectTask = null;
    }

    close() {
        this.ws.close();
    }

    connect() {
        this.ws = new WebSocket(this.url);

        // 当连接打开时，发送所有缓存的消息，并调用处理函数
        this.ws.onopen = () => {
            if (this.reconnectTask !== null) {
                clearInterval(this.reconnectTask)
                this.reconnectTask = null
            }
            while (this.messageQueue.length > 0) {
                let message = this.messageQueue.shift();
                this.raw_send(message)
            }
            if (this.handlers.onopen) {
                this.handlers.onopen();
            }
        };

        // 当接收到消息时，调用处理函数
        this.ws.onmessage = (event) => {
            this.stats.received.count++;
            this.stats.received.length += event.data.length;
            if (this.handlers.onmessage) {
                this.handlers.onmessage(event);
            }
        };

        // 当连接关闭时，尝试重新连接，并调用处理函数
        this.ws.onclose = () => {
            this.ws = null
            this.connect()
            if (this.handlers.onclose) {
                this.handlers.onclose();
            }
        };
    }

    send(data, ignore = false) {
        let message;
        if (!ignore) {
                if ((typeof data === 'object' && !Array.isArray(data)) || Array.isArray(data)) {
                // 如果数据是一个对象（不包括数组），则将其转换为JSON字符串
                message = JSON.stringify(data);
            } else {
                // 否则，将数据转换为字符串
                message = String(data);
            }
        } else message = data

        this.raw_send(message)
    }
    raw_send(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.stats.sent.count++;
            this.stats.sent.length += message.length;
            this.ws.send(message);
        } else {
            if (!this.ws || this.ws.readyState === WebSocket.CLOSED) {
                this.connect();
            }
            this.messageQueue.push(message);
        }
    }

    getStats() {
        return this.stats;
    }
}
class MinecraftUtils {
    static getVarInt(data) {
        let r = [];
        while (true) {
            if ((data & 0xFFFFFF80) === 0) {
                r.push(data);
                break;
            }
            r.push(data & 0x7F | 0x80);
            data >>= 7;
        }
        return r;
    }
    static getVarIntLength(data) {
        return this.getVarInt(data).length;
    }
}
class BytesBuffer {
    constructor(...data) {
        this.buffer = []
        this.cur = 0
        this.write(...data)
    }
    write(...values) {
        for (const value of values) {
            if (value instanceof BytesBuffer) {
                this.buffer.push(...value.buffer)
            } else if (Number.isInteger(value)) {
                this.buffer.push(value < 0 ? value + 256 : value)
            } else if (Array.isArray(value) && value.filter(v => Number.isInteger(v)).length == value.length) {
                value.forEach(v => this.write(v))
            } else if (value instanceof Uint8Array) {
                for (let i = 0; i < value.byteLength; i++) {
                    this.write(value[i])
                }
            } else if (value instanceof ArrayBuffer) {
                this.write(new Uint8Array(value))
            } else if (!value === undefined) {
                console.log(typeof value, "buf", value)
            }
        }
    }
    read(length = 1) {
        let data = []
        for (let i = 0; i < length; i++) data.push(...this.buffer.slice(this.cur + i, this.cur + i + 1))
        this.cur += length
        return data;
    }
    tell() {
        return this.cur
    }
    readBytes(length) {
        return this.read(length);
    }
    sizeof() {
        return this.buffer.length;
    }
    len() {
        return this.buffer.length;
    }
    toBytes() {
        return new Uint8Array(this.buffer)
    }
    copy() {
        let buf = []
        this.buffer.forEach(v => buf.push(v))
        return buf
    }
}
class DataOutputStream extends BytesBuffer {
    constructor(data) {
        super()
        this.write(data)
    }
    writeInteger(value) {
        this.write((value >> 24) & 0xFF, (value >> 16) & 0xFF, (value >> 8) & 0xFF, (value >> 0) & 0xFF);
    }
    writeBoolean(value) {
        this.write(value ? 1 : 0)
    }
    writeFloat(value) {
        const bytes = new Uint8Array((new Float32Array([value])).buffer);  
        for (let i = 0; i < 4; i++) {  
            this.write(bytes[i]);  
        }  
    }
    writeDouble(value) {
        const bytes = new Uint8Array((new Float64Array([value])).buffer);  
        for (let i = 0; i < 8; i++) {  
            this.write(bytes[i]);  
        }  
    }
    writeVarInt(value) {
        this.write(MinecraftUtils.getVarInt(value));
        return this;
    }
    writeString(data, encoding = 'utf-8') {
        this.writeVarInt(data.length);
        this.write(new TextEncoder(encoding).encode(data));
        return this;
    }
    writeLong(data) {
        data = data - (data > Math.pow(2, 63) - 1 ? Math.pow(2, 64) : data);
        this.write((data >> 56) & 0xFF, (data >> 48) & 0xFF, (data >> 40) & 0xFF, (data >> 32) & 0xFF, (data >> 24) & 0xFF, (data >> 16) & 0xFF, (data >> 8) & 0xFF, (data >> 0) & 0xFF);
        return this;
    }
    writeUUID(uuid) {
        this.writeLong(uuid.int >> 64);
        this.writeLong(uuid.int & ((1 << 64) - 1));
        return this;
    }
}
class DataInputStream extends BytesBuffer {
    readInteger() {
        let value = this.read(4)
        return ((value[0] << 24) + (value[1] << 16) + (value[2] << 8) + (value[3] << 0))
    }
    readBoolean() {
        return Boolean(this.read(1)[0]);
    }
    readShort() {
        value = this.read(2);
        if (value[0] | value[1] < 0)
            throw EOFError()
        return ((value[0] << 8) + (value[1] << 0))
    }
    readLong() {
        let value = this.read(8)
        value = (
            (value[0] << 56) +
            ((value[1] & 255) << 48) +
            ((value[2] & 255) << 40) +
            ((value[3] & 255) << 32) +
            ((value[4] & 255) << 24) +
            ((value[5] & 255) << 16) +
            ((value[6] & 255) << 8) +
            ((value[7] & 255) << 0))
        return value < BigInt(Math.pow(2, 63) - 1) ? value : value - BigInt(Math.pow(2, 64));
    }
    readDouble() {
        return (new DataView(new Uint8Array(this.readBytes(4)))).getFloat64()
    }
    readFloat() {
        return (new DataView(new Uint8Array(this.readBytes(4)))).getFloat32()
    }
    readVarInt() {
        let i = 0;
        let j = 0;
        let k;
        while (true) {
            k = this.read(1)[0];
            i |= (k & 0x7F) << j * 7;
            j += 1;
            if (j > 5) throw new Error("VarInt too big");
            if ((k & 0x80) !== 128) break;
        }
        return i >= 2 ** 31 - 1 ? i - 2 ** 31 * 2 : i;
    }
    readString(maximum = null, encoding = 'utf-8') {
        return new TextDecoder(encoding).decode(new Uint8Array(this.read(maximum == null ? this.readVarInt() : maximum)));
    }
    readBytes(length) {
        return this.read(length);
    }
    readUUID() {
        let m = this.readLong();
        let l = this.readLong();
        return new UUID(m.toBytes().concat(l.toBytes()));
    }
}
const deserializeData = (input) => {
    const type = input.readVarInt()
    switch (type) {
        case 0: // string
            return input.readString()
        case 1: // int
            return input.readBoolean()
        case 2: // float
            return parseFloat(input.readString())
        case 3: // bool
            return parseInt(input.readString())
        case 4: {// list
            const length = input.readVarInt()
            const data = []
            for (let _ = 0; _ < length; _++) data.push(deserializeData(input))
            return data
        }
        case 5: {// table
            const length = input.readVarInt()
            const data = {}
            for (let _ = 0; _ < length; _++) {
                data[deserializeData(input)] = deserializeData(input)
            }
            return data
        }
        default:
            console.log(type)
            return null
    }
}
const ExtendFlex = () => {
    class ExtendFlex extends ExtendElements {
        constructor() {
            super("div")
            this.css("extend-flex")
        }
        append(...elements) {
            super.append(...elements.map(e => e.valueOf()))
            return this
        }
        width(value) {
            if (typeof value === "number") value += "px";
            this.valueOf().style.width = value
            return this
        }
        height(value) {
            if (typeof value === "number") value += "px";
            this.valueOf().style.height = value
            return this
        }
        childWidth(...value) {
            let i = 0
            for (const v of value) {
                if (this.parent.children.length == i) return this
                if (typeof v === "number") v += "px";
                this.parent.children[i].style.width = v
                i++
            }
            return this
        }
        childHeight(...value) {
            let i = 0
            for (const v of value) {
                if (this.parent.children.length == i) return this
                if (typeof v === "number") v += "px";
                this.parent.children[i].style.height = v
                i++
            }
            return this
        }
    }
    return new ExtendFlex()
}
const sum = (...arr) => {
    let i = 0;
    for (v of arr) i += v
    return i
}
const formatterDate = (date) => {
    date = date ? date : new Date();
    return date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate() + " " + date.getHours().toString().padStart(2, 0) + ":" + date.getMinutes().toString().padStart(2, 0) + ":" + date.getSeconds().toString().padStart(2, 0)
}
const ExtendCheckbox = (def = false) => {
    class ExtendCheckbox {
        constructor(default_ = false) {
            this.parent = ExtendElement("div").css("extend-checkbox")
            this.last = default_
            this.setValue(this.last)
            this.handler = () => {
                return 1;
            }
            this.parent.event("click", () => {
                if (this.handler(this)) this.setValue(!this.last)
            })
        }
        setValue(bool) {
            this.last = bool
            if (bool) this.parent.valueOf().classList.add("checked")
            else this.parent.valueOf().classList.remove("checked")
            return this
        }
        getValue() {
            return this.last
        }
        setHandler(handler) {
            this.handler = handler ? handler : () => { return 1; }
            return this
        }
        valueOf() {
            return this.parent.valueOf()
        }
    }
    return new ExtendCheckbox(def)
}
const ExtendInput = (type) => {
    class ExtendInputUnit extends ExtendElements {
        constructor() {
            super("div")
            this.input = ExtendElement("input")
            super.css("extend-input").append(
                ExtendElement("label").valueOf(),
                ExtendElement("div").css("input-unit").append(
                    this.input.valueOf(),
                    ExtendElement("div").css("tips").append(
                        ExtendElement("p").valueOf()
                    ).valueOf(),
                    ExtendElement("fieldset").append(
                        ExtendElement("legend").append(
                            ExtendElement("span").valueOf()
                        ).valueOf()
                    ).valueOf()
                ).valueOf()
            )
            this.force_value = false
            this.input.event("focus", () => {
                super.css("active")
            })
            this.input.event("blur", () => {
                if (!this.input.valueOf().value) super.rcss("active")
            })
            this.label = ""
            this.unit = ""
        }
        setUnit(text) {
            this.unit = text
            this.force(this.force_value)
            return this
        }
        setLabel(text) {
            this.label = text
            this.force(this.force_value)
            return this
        }
        setType(type) {
            this.input.valueOf().type = type
            return this
        }
        force(value) {
            this.force_value = value ? value : false
            this.parent.children[1].children[1].children[0].innerText = this.unit
            this.parent.children[0].innerText = this.label
            this.parent.children[1].children[2].children[0].children[0].innerText = this.label
            if (this.force_value) {
                this.parent.children[0].append(ExtendElement("span").text("*").css("must").valueOf())
                this.parent.children[1].children[2].children[0].children[0].append(ExtendElement("span").text("*").css("must").valueOf())
            }
            return this
        }
        setValue(value) {
            this.input.value(value)
            if (value === '') super.rcss("active")
            else super.css("active")
            return this
        }
        event(name, handler) {
            this.input.event(name, handler)
            return this
        }
        setMin(value) {
            this.input.setAttr("min", value);
            return this
        }
        setMax(value) {
            this.input.setAttr("max", value);
            return this
        }
        setLength(value) {
            this.input.setAttr("length", value);
            return this
        }
    }
    class ExtendInputOption extends ExtendElements {
        constructor() {
            super("div")
            this.input = ExtendElement("div")
            super.css("extend-input").append(
                ExtendElement("label").valueOf(),
                ExtendElement("div").css("input").append(
                    this.input.css("input-full").valueOf(),
                    ExtendElement("fieldset").append(
                        ExtendElement("legend").append(
                            ExtendElement("span").valueOf()
                        ).valueOf()
                    ).valueOf()
                ).valueOf()
            )
            super.css("active")
            this.input.event("focus", () => {
                super.css("active")
            })
            this.input.event("blur", () => {
                if (!this.input.valueOf().value) super.rcss("active")
            })
        }
        setLabel(text) {
            this.label = text
            this.parent.children[0].innerText = this.label
            this.parent.children[1].children[this.parent.children[1].children.length - 1].children[0].children[0].innerText = this.label
            return this
        }
        setData(data) {
            this.data = data
            return this
        }
    }
    switch (type) {
        case "unit":
            return new ExtendInputUnit()
        case "option":
            return new ExtendInputOption()
        default:
            throw TypeError("Not found type: " + unit)
    }
}
var Extendi18nLanguage = "zh_cn"
const Extendi18nTable = {}
const Extendi18nSet = (lang, key, value) => {
    if (!(lang in Extendi18nTable)) Extendi18nTable[lang] = {}
    Extendi18nTable[lang][key] = value
    return Extendi18nSet
}
const Extendi18nSets = (lang, table) => {
    for (const key in table) {
        const value = table[key]
        Extendi18nSet(lang, key, value)
    }
}
const Extendi18n = (key) => { return (!(Extendi18nLanguage in Extendi18nTable) || !(key in Extendi18nTable[Extendi18nLanguage])) ? key : Extendi18nTable[Extendi18nLanguage][key] }
const getURLParams = () => {return window.location.hash.indexOf("#") !== -1 ? window.location.hash.slice(1) : ""}
const getURLKey = () => {
    var key = getURLParams()
    return (key.startsWith("/") ? key.slice(1) : key).slice(0, key.indexOf("?") !== -1 ? key.indexOf("?") : key.length)
}
const getURLKeyParams = () => {
    var key = getURLParams()
    key = key.startsWith("/") ? key.slice(1) : key
    if (key.indexOf("?") !== -1) {
        var params = {};
        var queries = (key.slice(key.indexOf("?"))).substring(1).split("&");
        for (var i = 0; i < queries.length; i++) {
            var pair = queries[i].split('=');
            if (pair[0]) params[decodeURIComponent(pair[0])] = decodeURIComponent(pair[1] || '');
        }
        return params;
    }
    return {}
}
const getURLSearch = (search = null) => {
    var key = search != null ? search : window.location.search;
    if (key.indexOf("?") !== -1) {
        var params = {};
        var queries = (key.slice(key.indexOf("?"))).substring(1).split("&");

        for (var i = 0; i < queries.length; i++) {
            var pair = queries[i].split('=');
            if (pair[0]) params[decodeURIComponent(pair[0])] = decodeURIComponent(pair[1] || '');
        }
        return params;
    }
}
const setURLSearch = (params) => {
    var content = '?'
    for (k in params) {
        v = params[k]
        if (!v) continue
        content += encodeURIComponent(k) + "=" + encodeURIComponent(v) + "&"
    }
    return content.slice(0, content.length - 1)
}
const getTimestamp = () => { return (new Date()).valueOf() }
const ExtendConfig = {
    "alert": {
        "fadeIn": 1000,
        "stay": 5000,
        "fadeOut": 2000,
        "stack": false
    },
    "notification": {
        "fadeIn": 2000,
        "stay": 5000,
        "fadeOut": 2000,
        "stack": false
    },
    "defPageIcon": {
        "warn": () => {
            //<svg class="MuiSvgIcon-root MuiSvgIcon-fontSizeMedium css-33hd0d" focusable="false" aria-hidden="true" viewBox="0 0 24 24" data-testid="ErrorIcon"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2m1 15h-2v-2h2zm0-4h-2V7h2z"></path></svg>
            return '<svg viewbox="0 0 24 24" focusable="false" aria-hidden="true" style="user-select: none; width: 1em; height: 1em; display: inline-block; fill: currentcolor; flex-shrink: 0; transition: fill 200ms cubic-bezier(0.4, 0, 0.2, 1) 0ms; color: rgb(255, 191, 0); margin-right: 16px; font-size: 24px;"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2m1 15h-2v-2h2zm0-4h-2V7h2z" style="user-select: none; width: 1em; height: 1em; display: inline-block; fill: currentcolor; flex-shrink: 0; transition: fill 200ms cubic-bezier(0.4, 0, 0.2, 1) 0ms; color: rgb(255, 191, 0); margin-right: 16px; font-size: 24px;"></path></svg>'
        }
    },
}
const ExtendCache = {
    "alert": [],
    "notification": []
}
class ExtendPageObject {
    constructor() {
        this.header = ExtendElement("div").css("header").valueOf()
        this.titleElement = ExtendElement("div").valueOf()
        this.headerClose = ExtendElement("button").css("close").html('<svg class="svg" focusable="false" aria-hidden="true" viewBox="0 0 24 24" data-testid="CloseIcon"><path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"></path></svg><span class="MuiTouchRipple-root css-w0pj6f"></span>').valueOf()
        this.header.append(this.titleElement, this.headerClose)
        
        this.bodyElement = ExtendElement("div").css("body").valueOf()
        
        this.footer = ExtendElement("div").css("footer").valueOf()
        this.cancel = ExtendElement("button").css("cancel").text("取消").valueOf()
        this.confirm = ExtendElement("button").css("confirm").text("确定").valueOf()
        this.footer.append(this.cancel, this.confirm);
        
        this.confirmHandler = () => { return 1; };
        this.cancelHandler = () => { return 1; };

        window.addEventListener("click", (event) => { if (event.target.classList.contains("panel") || event.target.classList.contains("extend-panel-container")) if (this.cancelHandler()) this.destroy() })
        this.cancel.addEventListener("click", () => { if (this.cancelHandler()) this.destroy() })
        this.headerClose.addEventListener("click", () => { if (this.cancelHandler()) this.destroy() })
        this.confirm.addEventListener("click", () => {
            if (this.confirmHandler()) this.destroy()
        })
        this.node = ExtendElement("div").css("extend-panel-container", "close").append(ExtendElement("div").css("panel").append(ExtendElement("div").css("paper").append(this.header, this.bodyElement, this.footer).valueOf()).valueOf()).valueOf()
    }
    title(text) {
        while (this.titleElement.firstChild != null) this.titleElement.removeChild(this.titleElement.firstChild)
        this.titleElement.append(isDOM(text) ? text : ExtendElement("div").html(text).valueOf())
        return this
    }
    body(element) {
        this.bodyElement.append(isDOM(element) ? element : ExtendElement("div").html(element).valueOf())
        return this;
    }
    destroy() {
        if (this.node in document.body.children)
            document.body.removeChild(this.node)
        return this
    }
    open() {
        document.body.prepend(this.node)
        document.getElementsByClassName("extend-panel-container")[0].style = "top: " + window.scrollY + "px; left: " + window.scrollX + "px;"
        document.getElementsByClassName("extend-panel-container")[0].style.left = window.scrollX
        document.body.style.overflow = "hidden"
        document.getElementsByClassName("extend-panel-container")[0].classList.remove("close")
        return this
    }
    thenClose(handler) {
        this.cancelHandler = handler == null ? () => { return 1; } : handler
        return this
    }
    thenConfirm(handler) {
        this.confirmHandler = handler == null ? () => { return 1; } : handler
        return this
    }
    moreTitle(title) {
        const text = Extendi18n("extend.page.title." + title)
        const icon = title in ExtendConfig.defPageIcon ? ExtendConfig.defPageIcon[title]() : ""
        const div = ExtendFlex().append(ExtendElement("div").html(icon).valueOf(), text).valueOf()
        this.title(div)
        return this
    }
}
const ExtendTableList = () => {
    class ExtendTableList {
        constructor() {
            this.id = "extend-table-" + randomUUID()
            this.headerElement = ExtendElement("div").css("header")
            this.headerData = []
            this.containerData = []
            this.container = ExtendElement("div").css("container")
            this.body = ExtendElement("div").css("extend-table").id(this.id).append(this.headerElement.valueOf(), this.container.valueOf())
            this.headerRow = null
        }
        setHeaderRow(row) {
            this.headerRow = (Array.isArray(row) ? row : [row]).map(value => {
                if (Array.isArray(value)) return value.map(v => (v / value.reduce((a, b) => a + b, 0)) * 100);  
                else if (typeof value === 'string' && value.endsWith('%')) return parseFloat(value.replace('%', '')) / 100;  
                else return value;    
            });  
            this.headerElement.clear()
            this.headerElement.append(...this.headerData.map(v => ExtendElement("div").html(v).valueOf()))
            return this
        }
        header(data) {
            this.headerData = (Array.isArray(data) ? data : [data])
            this.headerElement.clear()
            this.headerElement.append(...this.headerData.map(v => ExtendElement("div").html(v).valueOf()))
            return this
        }
        element() {
            return this.body.valueOf()
        }
        width(value) {
            this.body.style("width: " + value)
            return this
        }
    }
    return new ExtendTableList()
}
const ExtendPage = new ExtendPageObject()
const Extend = {
    "alert": {
        "setConfig": (key, value) => { if (key in ExtendConfig.alert) ExtendConfig.alert[key] = value },
        "getConfig": (key, def) => { return key in ExtendConfig.alert ? ExtendConfig.alert[key] : def },
        "message": (message) => {
            ExtendCache.alert.push({
                "message": message,
                "startAt": getTimestamp()
            })
        }
    },
    "notification": {
        "setConfig": (key, value) => { if (key in ExtendConfig.notification) ExtendConfig.notification[key] = value },
        "getConfig": (key, def) => { return key in ExtendConfig.notification ? ExtendConfig.notification[key] : def },
        "message": (message) => {
            ExtendCache.notification.push({
                "message": message,
                "startAt": getTimestamp()
            })
        }
    },
    "page": ExtendPage,
    "format_number": (n) => {
        var d = (n + "").split("."), i = d[0], f = d.length >= 2 ? "." + d.slice(1).join(".") : ""
        return i.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",") + f;
    },
    "calc_byte": (arr) => {
        let max = Math.max(...arr)
        let sub = 0
        while (max >= 1024.0 && sub < Extend.sub_bytes.length - 1) {
            max /= 1024.0
            sub++
        }
        arr = arr.map(val => val / Math.pow(1024, sub))
        return {value: arr, byte: Extend.sub_bytes[sub]}
    },
    "calc_bytes": (arr) => {
        arr = arr.map(val => val * 8)
        let max = Math.max(...arr)
        let sub = 0
        while (max >= 1000.0 && sub < Extend.sub_bytes.length - 1) {
            max /= 1000.0
            sub++
        }
        arr = arr.map(val => val / Math.pow(1000, sub))
        return {value: arr, byte: Extend.sub_bytes[sub]}
    },
    'sub_bytes': ['B', 'Kb', 'Mb', 'Gb', 'Tb']

};
const randomUUID = () => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
    })
}
const isDOM = (value) => { return value instanceof HTMLElement ||  
    Object.prototype.toString.call(value) === '[object HTMLUnknownElement]' ||  
    (value && typeof value === 'object' && value.nodeType === 1 && typeof value.nodeName === 'string');  
};
const css = document.createElement("style");
document.head.append(css)
const styles = {}
const set_styles = (table) => {
    for (const key in table) {
        set_style(key, table[key])
    }
    return set_styles
}
const set_style = (tag, code) => {
    const styleRule = `${tag} { ${code} }`;  
    const textNode = document.createTextNode(styleRule);  
    const styleSheet = css.sheet;  
    if (styleSheet) {  
        try {  
            styleSheet.insertRule(styleRule, styleSheet.cssRules.length);  
        } catch (e) { 
            css.appendChild(textNode);  
        }  
    } else {
        css.appendChild(textNode);  
    }  
    styles[tag] = code;    
    return set_style;  
};  
(function () {
    set_styles(extend_default_styles)
    let alert = document.createElement("div")
    let notification = document.createElement("div")
    alert.id = "extend-alerts"
    notification.id = "extend-notifications"
    document.body.append(alert, notification)
    const notificationProcess = () => {
        var currentTime = getTimestamp();
        var messageHeight = 0;
        var fadeIn = ExtendConfig.notification.fadeIn, stay = ExtendConfig.notification.stay, fadeOut = ExtendConfig.notification.fadeOut
        for (let i = ExtendCache.notification.length - 1; i >= 0; i--) {
            let msg = ExtendCache.notification[i];
            if (msg.id == null) {
                msg.id = randomUUID()
                var div = isDOM(msg.message) ? msg.message : (() => { let body = document.createElement("div"); body.innerHTML = msg.message; return body; })()
                div.id = "extend-notification-" + msg.id
                document.getElementById("extend-notifications").insertBefore(div, document.getElementById("extend-notifications").firstChild);
            }
            document.getElementById("extend-notification-" + msg.id).style.bottom = "calc(10vh + " + messageHeight + "px)";
            messageHeight += document.getElementById("extend-notification-" + msg.id).offsetHeight;
            if (currentTime >= msg.startAt + fadeIn + stay + fadeOut) {
                document.getElementById("extend-notification-" + msg.id).remove()
                ExtendCache.notification.splice(i, 1);
            } else if (currentTime >= msg.startAt + fadeIn + stay) {
                if (document.getElementById("extend-notification-" + msg.id).classList.contains("show")) {
                    document.getElementById("extend-notification-" + msg.id).style.transitionDuration = fadeOut + "ms";
                    document.getElementById("extend-notification-" + msg.id).classList.remove("show")
                }
            } else if (currentTime >= msg.startAt + fadeIn + 50) {
                document.getElementById("extend-notification-" + msg.id).style.transitionDuration = "0ms";
            } else if (currentTime >= msg.startAt) {
                document.getElementById("extend-notification-" + msg.id).style.transitionDuration = fadeIn + "ms";
                document.getElementById("extend-notification-" + msg.id).classList.add("show");
            }
        }
    }
    const alertProcess = () => {
        var currentTime = getTimestamp();
        var messageHeight = 0;
        var fadeIn = ExtendConfig.alert.fadeIn, stay = ExtendConfig.alert.stay, fadeOut = ExtendConfig.alert.fadeOut
        for (let i = ExtendCache.alert.length - 1; i >= 0; i--) {
            let msg = ExtendCache.alert[i];
            if (msg.id == null) {
                msg.id = randomUUID()
                var div = isDOM(msg.message) ? msg.message : (() => { let body = document.createElement("div"); body.innerHTML = msg.message; return body; })()
                div.id = "extend-alert-" + msg.id
                document.getElementById("extend-alerts").insertBefore(div, document.getElementById("extend-alerts").firstChild);
            }
            document.getElementById("extend-alert-" + msg.id).style.top = "calc(2vh + " + messageHeight + "px)";
            messageHeight += document.getElementById("extend-alert-" + msg.id).offsetHeight;
            if (currentTime >= msg.startAt + fadeIn + stay + fadeOut) {
                document.getElementById("extend-alert-" + msg.id).remove()
                ExtendCache.alert.splice(i, 1);
            } else if (currentTime >= msg.startAt + fadeIn + stay) {
                if (document.getElementById("extend-alert-" + msg.id).classList.contains("show")) {
                    document.getElementById("extend-alert-" + msg.id).style.transitionDuration = fadeOut + "ms";
                    document.getElementById("extend-alert-" + msg.id).classList.remove("show")
                }
            } else if (currentTime >= msg.startAt + fadeIn + 50) {
                document.getElementById("extend-alert-" + msg.id).style.transitionDuration = "0ms";
            } else if (currentTime >= msg.startAt) {
                document.getElementById("extend-alert-" + msg.id).style.transitionDuration = fadeIn + "ms";
                document.getElementById("extend-alert-" + msg.id).classList.add("show");
            }
        }
    }
    Extendi18nSets("zh_cn", {
        "extend.page.title.warn": "警告",
        "extend.page.title.error": "报错"
    })
    Extendi18nSets("en_us", {
        "extend.page.title.warn": "Warning",
        "extend.page.title.error": "Error"
    })
    setInterval(() => {
        notificationProcess()
        alertProcess()
    })
})();


//document.body.append(ExtendTableList().header(["121", "113"]).element())