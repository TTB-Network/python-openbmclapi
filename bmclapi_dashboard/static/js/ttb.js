class TTBElement {
    constructor(tag, isElement = false) {
        this.base = isElement ? tag : document.createElement(tag)
        this._resize_handler = []
        window.addEventListener("resize", (...event) => this._resize(...event))
    }
    setHTML(content) {
        this.base.innerHTML = content;
        return this
    }
    setText(content) {
        this.base.innerText = content;
        return this
    }
    title(content) {
        return this.setText(content)
    }
    html(content) {
        return this.setHTML(content)
    }
    append(...elements) {
        for (const element of elements) {
            if (element instanceof TTBElement) {
                this.base.append(element.valueOf())
            } else {
                this.base.append(element)
            }
        }
        return this
    }
    id(name) {
        this.base.id = name
        return this
    }
    class(...classes) {
        for (const clazz of classes) {
            for (const cls of clazz.split(" ")) this.base.classList.add(cls)
        }
        return this
    }
    toggle(clazz) {
        this.base.classList.toggle(clazz)
        return this;
    }
    style(style) {
        this.base.style = style
        return this;
    }
    _resize(...event) {
        for (const func of this._resize_handler) {
            try {
                func(...event)
            } catch (e) {
                console.log(e, func)
            }
        }
    }
    setStyle(key, value) {
        this.base.style[key] = value
        return this;
    }
    valueOf() {
        return this.base
    }
    containsClass(...classes) {
        for (const clazz of classes) {
            for (const cls of clazz.split(" ")) if (this.base.classList.contains(cls)) return true
        }
        return false
    }
    setAttribute(key, value) {
        this.base.setAttribute(key, value)
        return this
    }
    isDOM(value) { return value instanceof HTMLElement ||  
        Object.prototype.toString.call(value) === '[object HTMLUnknownElement]' ||  
        (value && typeof value === 'object' && value.nodeType === 1 && typeof value.nodeName === 'string');  
    };
    clear() {
        while (this.base.firstChild != null) this.base.removeChild(this.base.firstChild)
        return this
    }
    event(name, func) {
        if (name == "resize") {
            this._resize_handler.push(func)
            return this
        }
        this.base.addEventListener(name, func)
        return this
    }
    getChildrens() {
        return new Array(...this.base.children).map(v => {
            if (this.isDOM(v) && v.classList.contains("ttb-flex")) return new TTBElementFlex(v, true)
            return new TTBElement(v, true)
        })
    }
}
class TTBElementFlex extends TTBElement {
    constructor(tag = "div", isElement = false) {
        super(tag, isElement)
        this.class("ttb-flex")
        this._minwidth  = null
        this._minheight = null
        this._maxwidth  = null
        this._maxheight = null
        this._updateTimer = null
        this._child = 1
        this._childStyle = ''
        this._tag = null
        window.addEventListener("resize", () => this.update())
        setTimeout(() => this.update(), 5)
    }
    append(...elements) {
        super.append(...elements.map(e => this.isDOM(e) || e instanceof TTBElement ? e : (new TTBElement("div")).setHTML(e)))
        this.update()
        return this
    }
    tag(tag) {
        this._tag = tag
        return this
    }
    min_width(width) {
        this.minwidth = width
        this.update()
        return this
    }
    max_width(width) {
        this.maxwidth = width
        this.update()
        return this
    }
    min_height(height) {
        this.minheight = height
        this.update()
        return this
    }
    max_height(height) {
        this.maxheight = height
        this.update()
        return this
    }
    height(height) {
        this.setStyle("height", height)
        return this
    }
    width(width) {
        this.setStyle("width", width)
        return this
    }
    style(key, value) {
        g_TTB.set_style(".ttb-flex." + key + "_" + value, `${key}: ${value}`)
        this.class(key + "_" + value)
        return this
    }
    update() {
        this._update();
        return this;
    }
    _update() {
        const width = (super.valueOf().offsetWidth - 1)
        let minwidth = this._calcValueWithDisplay(this._minwidth || 0, width)
        let maxwidth = this._calcValueWithDisplay(this._maxwidth, width)
        let newwidth = g_TTB.clamp(minwidth, width, maxwidth)
        const width_avg = Math.max(0, Math.floor((newwidth - 1) / this._child))
        for (const child of this.getChildrens()) {
            const child_style = window.getComputedStyle(child.valueOf())
            const margin = (parseInt(child_style.marginRight, 10) + parseInt(child_style.marginLeft, 10))
            child.valueOf().style = this._childStyle
            child.setStyle("boxSizing", "border-box")
            child.setStyle("width", (newwidth < minwidth ? width : (width_avg - (Number.isNaN(margin) ? 0 : margin))) + "px")
        }
        this.getChildrens().filter(v => v instanceof TTBElementFlex).forEach(v => v.update())
        this._resize()
    }
    _calcValueWithDisplay(value, display) { 
        if (value == -1 || value == null) return display
        if (typeof value === 'string' && value.includes('%')) {  
            return Math.floor(display * (parseFloat(value.replace('%', '')) / 100));  
        } else {  
            return value;  
        }  
    }  
    childStyle(value) {
        this._childStyle = value
        this.update()
        return this
    }
    minWidth(value) {
        this._minwidth = value
        this.update()
        return this
    }
    minHeight(value) {
        this._minheight = value
        this.update()
        return this
    }
    maxWidth(value) {
        this._maxwidth = value
        this.update()
        return this
    }
    maxHeight(value) {
        this._maxheight = value
        this.update()
        return this
    }
    child(value) {
        this._child = Math.max(1, Number.parseInt(value.toString()))
        this.update()
        return this
    }
}
class WebSocketClient {  
    constructor(parameters = {}) {  
        this.url = parameters.url;  
        this.socket = null;  
        this.reconnectAttempts = 0;  
        this.maxReconnectAttempts = 5; // 最大重连尝试次数  
        this.reconnectInterval = 5000; // 重连间隔（毫秒）  
        this.parameters = parameters;  
        this.websockets = []; // 假设这个列表用于存储所有的WebSocketClient实例  
  
        this.initWebSocket();  
    }  
  
    initWebSocket() {  
        this.socket = new WebSocket(this.url);  
        this.bindEvents();  
    }  
  
    bindEvents() {  
        this.socket.onopen = this.onOpen.bind(this);  
        this.socket.onclose = this.onClose.bind(this);  
        this.socket.onmessage = this.onMessage.bind(this);  
        this.socket.onerror = this.onError.bind(this);  
    }  
  
    onOpen() {  
        this.reconnectAttempts = 0; // 重置重连尝试次数  
        this.parameters.open && this.parameters.open(this);  
    }  
  
    onClose(event) {  
        this.reconnect(); // 尝试重连  
        this.parameters.close && this.parameters.close(event);  
    }  
  
    onMessage(event) {  
        this.parameters.message && this.parameters.message(event);  
    }  
  
    onError(event) {  
        this.reconnect(); // 在错误时也尝试重连  
        this.parameters.error && this.parameters.error(event);  
    }  
  
    send(data) {  
        if (this.socket.readyState === WebSocket.OPEN) {  
            this.socket.send(data instanceof BytesBuffer ? data.toBytes() : data);  
        } else {  
            this.close()
            console.warn('WebSocket is not open. Cannot send data.');  
            this.reconnect();
        }  
    }  
  
    close() {  
        if (this.socket) {  
            this.socket.close();  
        }  
        this.parameters.close && this.parameters.close()
    }  
  
    reconnect() {  
        if (this.reconnectAttempts < this.maxReconnectAttempts) {  
            setTimeout(() => {   
                this.initWebSocket(); // 尝试重新初始化WebSocket连接  
                this.reconnectAttempts++;  
            }, this.reconnectInterval);  
        } else {  
        }  
    }  
}  
class TTB {  
    constructor() {
        this.VERSION = "0.0.1"
        this.defaultStyles = {
            ".ttb-flex": [
                "display: flex",
                "flex-wrap: wrap"
            ]
        }
        this.websockets = []
        this.documentStyle = document.createElement("style");
        this.styles = {}
        this.set_styles(this.defaultStyles)
        document.head.append(this.documentStyle)
        window.addEventListener('beforeunload', () => {
            this.websockets.forEach(e => e.object.close())
        }); 
        g_TTB = this
    }
    createFlex() {
        return new TTBElementFlex()
    }
    createElement(tag) {
        return new TTBElement(tag)
    }
    request(parametars = {}) {  
        const method = parametars.method || "GET";  
        const url = parametars.path || "/";  
        const headers = parametars.headers || {};  
        const async = parametars.async !== false;
        const username = parametars.username || null;  
        const password = parametars.password || null;  
        const responseType = parametars.responseType || "text";  
        let xhr = new XMLHttpRequest();  
        xhr.open(method, url, async, username, password);  
        for (const key in headers) xhr.setRequestHeader(key, headers[key]);   
        xhr.responseType = responseType;  
        xhr = (parametars.xhr && parametars.xhr(xhr)) || xhr
        return new Promise((resolve, reject) => {  
            xhr.onload = function() {  
                if (xhr.status >= 200 && xhr.status < 300) {  
                    parametars.success && parametars.success(xhr.response);  
                    resolve(xhr.response);  
                } else {  
                    parametars.error && parametars.error(xhr.status, xhr.statusText);   
                    reject(new Error(`Request failed with status ${xhr.status}: ${xhr.statusText}`));  
                }  
            };  
            xhr.onerror = function () {  
                parametars.error && parametars.error(xhr.status, xhr.statusText);   
                reject(new Error('Network Error'));  
            };  
            xhr.send(parametars.data || null);  
        });  
    }
    websocket(parameters = {}) {  
        return new WebSocketClient(parameters)
    }
    set_styles = (table) => {
        for (const key in table) this.set_style(key, table[key])
    }
    set_style = (tag, code) => {
        if (Array.isArray(code)) code = code.join(";")
        const styleRule = `${tag} { ${code} }`;  
        const textNode = document.createTextNode(styleRule);  
        const styleSheet = this.documentStyle.sheet;  
        if (styleSheet) {  
            try {  
                styleSheet.insertRule(styleRule, styleSheet.cssRules.length);  
            } catch (e) { 
                this.documentStyle.appendChild(textNode);  
            }  
        } else {
            this.documentStyle.appendChild(textNode);  
        }  
        this.styles[tag] = code;  
    };  
    calculateBytes(data) {  
        let bytes;
        if (typeof data === "string") bytes = (new TextEncoder()).encode(data).byteLength
        else if (data instanceof ArrayBuffer || data instanceof DataView || data instanceof Uint8Array) bytes = data.byteLength;
        else if (data instanceof Blob) bytes = data.size
        else if (data instanceof BytesBuffer) bytes = data.len()
        else bytes = (new TextEncoder()).encode(String(data)).byteLength
        return bytes;  
    } 
    sum(...arr) {
        let total = 0;
        for (const value of arr) {
            total += value;
        }
        return total;
    }
    avg(...arr) {
        return arr.length == 0 ? 0 : this.sum(...arr) / arr.length
    }
    isDOM(value) { return value instanceof HTMLElement ||  
        Object.prototype.toString.call(value) === '[object HTMLUnknownElement]' ||  
        (value && typeof value === 'object' && value.nodeType === 1 && typeof value.nodeName === 'string');  
    }
    getURLParams() {return window.location.hash.indexOf("#") !== -1 ? window.location.hash.slice(1) : ""}
    getURLKey() {
        var key = this.getURLParams()
        return (key.startsWith("/") ? key.slice(1) : key).slice(0, key.indexOf("?") !== -1 ? key.indexOf("?") : key.length)
    }
    getURLKeyParams() {
        var key = this.getURLParams()
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
    getURLSearch(search = null) {
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
    setURLSearch(params) {
        var content = '?'
        for (k in params) {
            v = params[k]
            if (!v) continue
            content += encodeURIComponent(k) + "=" + encodeURIComponent(v) + "&"
        }
        return content.slice(0, content.length - 1)
    }
    getTimestamp(date) {
        return (date || new Date()).valueOf()
    }
    getTime(date) {
        return this.getTimestamp(date) / 1000.0
    }
    clamp(min, cur, max) {  
        return Math.max(min, Math.min(cur, max));  
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
g_TTB = null;