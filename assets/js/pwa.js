class ProgressiveWebApp {
    constructor() {
        if (!this.supportPWA()) {
            return;
        }
        this.register()
    }

    register() {
        navigator.serviceWorker.register('/service-worker.js').then(e => {
            console.log('Service Worker registered successfully', e);
        }).catch(e => {
            console.log('Service Worker registration failed', e);
        });
    }

    supportPWA() {
        return 'serviceWorker' in navigator;
    }
}

export const pwa = new ProgressiveWebApp();