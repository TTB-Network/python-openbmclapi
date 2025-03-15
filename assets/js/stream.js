export class TextEventStream {
    constructor(url) {
        this.url = url
        this.stream_send_func = null;
    }
    async connect() {
        this.instance = await fetch(
            this.url + "/receive", {
                method: 'GET',
            }
        )
    }
    send(data) {
        this.stream_send_func.enqueue(data);
    }
    close() {
        this.stream_send_func.close();
    }
    async read() {
        return await this.instance.body.getReader().read()
    }
}