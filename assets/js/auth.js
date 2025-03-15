var token = localStorage.getItem('auth-token');
var info = {};

export async function checkAuth() {
    if (token == null) return false;
    let resp = await fetch('/api/auth', {
        method: 'GET',
        headers: {
            'Authorization': token
        }
    })
    let status = resp.ok;
    if (!status) {
        localStorage.removeItem('auth-token');
        token = null;
    } else {
        info = await resp.json();
    }
    return status;
}
export async function refreshToken() {
    if (token == null) return;
    let resp = await fetch('/api/auth/issue', {
        method: 'GET',
        headers: {
            'Authorization': token
        }
    })
    if (resp.ok) {
        token = resp.headers.get('Authorization');
        localStorage.setItem('auth-token', token);
    }
    // maybe invalid token
    else localStorage.removeItem('auth-token');
    // trigger re-login
}
export async function login(username, password) {
    let resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username: username,
            password: password
        })
    })
    if (resp.ok) {
        let token = resp.headers.get('Authorization');
        localStorage.setItem('auth-token', token);
        return true;
    }
    return false;
}
export function initAuthAPI() {
    // fetch

    let oldFetch = window.fetch;
    window.fetch = async (url, options) => {
        if (token != null) {
            options.headers = {
                ...options.headers,
                'Authorization': token
            }
        }
        return await oldFetch(url, options);
    }
    // xhr
    let oldXMLHttpRequest = window.XMLHttpRequest;
    window.XMLHttpRequest = function () {
        var xhr = new oldXMLHttpRequest();
        xhr.addEventListener('readystatechange', function () {
            if (xhr.readyState == 4) {
                if (xhr.status == 401) {
                    localStorage.removeItem('auth-token');
                    window.location.href = '/auth/login';
                }
            }
        });
        return xhr;
    }
}
export function initAutoCheckAuth() {
    document.addEventListener('visibilitychange', async () => {
        if (document.visibilityState == 'visible') {
            if (!await checkAuth()) {
                localStorage.removeItem('auth-token');
                window.location.href = '/auth/login';
            }
        }
    })
}
initAuthAPI()