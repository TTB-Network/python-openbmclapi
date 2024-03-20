class TTBElement {
    constructor(tag) {
        this.base = document.createElement(tag)
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
        this.base.addEventListener(name, func)
        return this
    }
}
/*class TTBElementFlex extends TTBElement {
    constructor() {
        super("div")
        super.class("ttb-flex")
        this.minwidth = -1
        this.maxwidth = -1
        this.minheight = -1
        this.maxheight = -1
        window.addEventListener("resize", () => this._update())
    }   
    append(...elements) {
        super.append(...elements.map(e => this.isDOM(e) || e instanceof TTBElement ? e : (new TTBElement("div")).setHTML(e)))
        this.update()
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
        setTimeout(() => this._update(), 10)
    }
    _update() {
        const element = this.valueOf();
        const childWidths = this.getChildrenWidths();
        const childHeights = this.getChildrenHeights();

        // Calculate total width and height
        const totalWidth = childWidths.reduce((acc, val) => acc + val, 0);
        const totalHeight = childHeights.reduce((acc, val) => acc + val, 0);

        // Distribute remaining space if there are more than 2 child elements
        if (childWidths.length > 2) {
            const remainingWidth = window.innerWidth - totalWidth;
            const remainingHeight = window.innerHeight - totalHeight;

            // Distribute remaining width and height to the last child
            this.childWidth(childWidths[0], remainingWidth);
            this.childHeight(childHeights[0], remainingHeight);
        } else if (childWidths.length === 2) {
            // If there are exactly 2 child elements, split evenly
            const halfWidth = Math.floor(window.innerWidth / 2);
            const halfHeight = Math.floor(window.innerHeight / 2);

            this.childWidth(halfWidth, halfWidth);
            this.childHeight(halfHeight, halfHeight);
        }
    }
    childWidth(...value) {
        if (value.length == 1) value = value[0]
        const setValue = (i, v) => {
            if (typeof v === "number") v += "px";
            this.base.children[i].style.boxSizing = "border-box"
            this.base.children[i].style.width = v;
        }
        if (Array.isArray(value)) for (let i = 0; i < Math.min(value.length, this.base.children.length); i++) setValue(i, value[i])
        else for (let i = 0; i < this.base.children.length; i++) setValue(i, value)
        this.update()
        return this
    }
    childHeight(...value) {
        if (value.length == 1) value = value[0]
        const setValue = (i, v) => {
            if (typeof v === "number") v += "px";
            this.base.children[i].style.boxSizing = "border-box"
            this.base.children[i].style.height = v;
        }
        if (Array.isArray(value)) for (let i = 0; i < Math.min(value.length, this.base.children.length); i++) setValue(i, value[i])
        else for (let i = 0; i < this.base.children.length; i++) setValue(i, value)
        this.update()
        return this
    }
    getChildrenWidths() {  
        return Array(this.base.children).map(e => e.style && e.style.width || e.offsetWidth)
    }
    getChildrenHeights() {  
        return Array(this.base.children).map(e => e.style && e.style.height || e.offsetHeight)
    }
}*/
class TTBElementFlex extends TTBElement {
    constructor() {
        super("div")
        this._minwidth = -1
        this._minheight = -1
        this._maxwidth = -1
        this._maxheight - -1
        this._updateTimer = null
        this._child = 1
        this._childStyle = ''
        window.addEventListener("resize", () => this.update())
    }
    append(...elements) {
        super.append(...elements.map(e => this.isDOM(e) || e instanceof TTBElement ? e : (new TTBElement("div")).setHTML(e)))
        this.update()
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
        if (this._updateTimer) clearTimeout(this._updateTimer)
        this._updateTimer = setTimeout(() => this._update(), 100)
        return this
    }
    _update() {
        //console.log(super.valueOf().offsetHeight, super.valueOf().offsetWidth)
    }
    childStyle(value) {
        this._childStyle = value
        this.update()
        return this
    }
    minWidth(value) {
        this._minwidth = value
        return this
    }
    minHeight(value) {
        this._minheight = value
        return this
    }
    maxWidth(value) {
        this._maxwidth = value
        return this
    }
    maxHeight(value) {
        this._maxheight = value
        return this
    }
    child(value) {
        this._child = Math.max(1, Number.parseInt(value))
        return this
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
    websocket(parametars = {}) {
        const url = parametars.url;
        const socket = new WebSocket(url);
        const origin = {
            "status": true,
            "object": socket,
            "sendBytes": 0,
            "recvBytes": 0,
            "recvCount": 0,
            "sendCount": 0,
            "send": (data) => {
                socket.send(data instanceof BytesBuffer ? data.toBytes() : data)
                origin.sendBytes += this.calculateBytes(data)
                origin.sendCount ++
            },
            "close": () => {
                socket.close()
            }
        }
        this.websockets.push(origin)
        socket.onopen = () => {
            parametars.open && parametars.open(origin)
        }
        socket.onclose = (...event) => parametars.close && parametars.close(...event)
        socket.onmessage = (event) => {
            origin.recvBytes += this.calculateBytes(event.data)
            origin.recvCount ++
            parametars.message && parametars.message(event)
        }
        socket.onerror = (...event) => parametars.error && parametars.error(...event)
        return origin
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