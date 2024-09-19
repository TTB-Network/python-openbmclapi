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
        return uuid.join('').toLocaleLowerCase();
    }
}

class Socket {
    constructor(baseurl) {
        this._ws = null;
        this._wsReconnectTask = null;
        this._clientId = Utils.uuid();
        this._baseurl = baseurl;
        this._url = this._baseurl + "?id=" + this._clientId
        this._keepaliveTask = null;
        this._echoCallbacks = {}
        this._wsConnect()
        window.addEventListener("beforeunload", () => {
            this.send("disconnect")
            this._ws?.close()
        })
        setInterval(() => this._keepalive(), 5000);
        this._keepalive();
    }
    async _keepalive() {
        console.log(await this.send("keepalive", {
            "timestamp": new Date()
        }))
    }
    async _sendByXHR(event, data) {
        var xhr = new XMLHttpRequest();
        var echo_id = Utils.uuid();
        xhr.addEventListener("readystatechange", (event) => {
            if (event.target.readyState == XMLHttpRequest.DONE) {
                this._dispatchData(JSON.parse(xhr.response)); 
            }
        })
        xhr.open("POST", this._url);
        return this._setEchoCallback(echo_id, () => {
            xhr.send(JSON.stringify({
                "event": event,
                "data": data,
                echo_id
            }));
            setTimeout(() => {
                xhr.abort();
            }, 10000)
        });
    }
    _dispatchData(responses) {
        responses.forEach(response => {
            const { echo_id, event, data } = response;
            console.log(echo_id, event)
            if (echo_id == null) { // global dispatch event

            } else if (echo_id in this._echoCallbacks) {
                var { resolve, reject, timer } = this._echoCallbacks[echo_id];
                delete this._echoCallbacks[echo_id];
                clearTimeout(timer);
                resolve(data);
            }
        });
    }
    _wsConnect() {
        clearTimeout(this._wsReconnectTask)
        this._ws?.close()
        this._ws = new WebSocket(
            this._url
        )
        this._ws.addEventListener("close", () => {
            console.warn("The websocket has disconnected. After 5s to reconnect.")
            setTimeout(() => {
                this._wsConnect()
            }, 5000)
        })
        this._ws.addEventListener("message", (event) => {
            var raw_data = JSON.parse(event.data);
            this._dispatchData(raw_data)
        })
    }
    _sendByWs(event, data) {
        if (this._ws?.readyState != WebSocket.OPEN) return;
        var echo_id = Utils.uuid();
        return this._setEchoCallback(echo_id, () => {
            this._ws.send(JSON.stringify(
                {
                    "event": event,
                    "data": data,
                    echo_id
                }
            ))
        });
    }
    _setEchoCallback(id, executor) {
        return new Promise((resolve, reject) => {
            this._echoCallbacks[id] = { resolve, reject, timer: setTimeout(() => {
                reject("Timeout Error.")
            }, 10000)};
            executor();
        })
    }
    async send(event, data) {
        var handler = this._ws?.readyState == WebSocket.OPEN ? this._sendByWs : this._sendByXHR
        return handler.bind(this)(event, data);
    }
    
}

const $socket = new Socket(window.location.origin + "/api");
$socket.send("echo", "hello world")