class Utils {
    static uuid(len, radix) {
        var chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'.split('');
        var uuid = [], i;
        radix = radix || chars.length;
     
        if (len) {
            for (i = 0; i < len; i++) uuid[i] = chars[0 | Math.random()*radix];
        } else {
            var r;
            uuid[8] = uuid[13] = uuid[18] = uuid[23] = '-';
            uuid[14] = '4';
            for (i = 0; i < 36; i++) {
                if (!uuid[i]) {
                    r = 0 | Math.random()*16;
                    uuid[i] = chars[(i == 19) ? (r & 0x3) | 0x8 : r];
                }
            }
        }
        return uuid.join('');
    }
}

class Socket {
    constructor(baseurl) {
        this._baseurl = baseurl;
        this._ws = null;
        this._wsReconnectTask = null;
        this._wsConnect()
        window.addEventListener("beforeinput", () => {
            this._ws?.close()
        })
    }
    async _sendByFetch(event, data) {
        var resp = await fetch({
            "url": this._baseurl,
            "body": JSON.stringify(
                {
                    "event": event,
                    "data": data,
                    "echo_id": Utils.uuid()
                }
            )
        })
        return await resp.json()
    }
    _wsConnect() {
        clearTimeout(this._wsReconnectTask)
        this._ws?.close()
        this._ws = new WebSocket(
            this._baseurl
        )
        this._ws.addEventListener("close", () => {
            console.warn("The websocket has disconnected. After 5s to reconnect.")
            setTimeout(() => {
                this._wsConnect()
            }, 5000)
        })
        this._ws.addEventListener("message", (event) => {
            var raw_data = JSON.parse(event.data);
        })
    }
    async _sendByWs(event, data) {
        if (this._ws?.state != WebSocket.OPEN) return;
        var echo_id = Utils.uuid();
        this._ws.send({
            "event": event,
            "data": data,
            echo_id
        })
        var promise = new Promise((resolve, reject) => {
            
        });
        return promise;
    }
    async send(event, data) {
        if (this._ws != null && this._ws.state == WebSocket.OPEN) {
            return this._sendByWs(event, data)
        } else {
            return this._sendByFetch(event, data)
        }
    }
    
}

const $socket = new Socket(window.location.origin + "/api")