import { createApp, CTElement } from './cttb.js'
import { checkAuth, login } from './auth.js';
import { CTAlert, CTMenu, CTSVG, CTCard, CTCardText, CTFlex } from './componts.js';
import { TextEventStream } from './stream.js';


class AuthPage extends CTElement {
    constructor() {
        super("div");
        super.classes("auth-page")

        app.i18n.addLanguages('zh-cn', {
            'auth.title': '身份验证',
            'auth.username': '用户名',
            'auth.password': '密码',
            'auth.login': '登录'
        })

        app.i18n.addLanguages('en-us', {
            'auth.title': 'Authentication',
            'auth.username': 'Username',
            'auth.password': 'Password',
            'auth.login': 'Login'
        })


        this.username = CTElement.create("input").classes("auth-input").attr_i18n("placeholder", "auth.username").attr("type", "username")
        this.password = CTElement.create("input").classes("auth-input").attr_i18n("placeholder", "auth.password").attr("type", "password")
        this.box_username = CTElement.create("div").classes("auth-input-box").append(this.username)
        this.box_password = CTElement.create("div").classes("auth-input-box").append(this.password)
        this.button = CTElement.create("button").classes("auth-button").i18n("auth.login").listener("click", async () => {
            const username = this.username.inputValue || ''
            const password = this.password.inputValue || ''
            if (username.trim().length == 0 || password.trim().length == 0) {
                alerts.addAlert({
                    type: 'error',
                    message: '用户名或密码不能为空'
                })
                return;
            }
            // processing...
            super.clear()
            super.append(this.processing_container)
            this.processing_loading.style("display", "block")
            this.processing_success.style("display", "none")
            var res = false;
            try {
                res = await login(username, password)
            } catch (e) {
                alerts.addAlert({
                    type: 'error',
                    message: e.message
                })
            } finally {
                if (res) {
                    this.processing_loading.style("display", "none")
                    this.processing_success.style("display", "block")
                } else {
                    alerts.addAlert({
                        type: 'error',
                        message: '登录失败'
                    })
                    super.clear()
                    super.append(this.login_container)
                    return;
                }
                setTimeout(() => {
                    //super.clear()
                    if (res) {
                        app.route("/")
                    } else {
                        super.clear()
                        super.append(this.login_container)
                    }
                }, 2000)
            }
        })
        this.form = CTElement.create("div").classes("auth-form").append(
            this.box_username,
            this.box_password
        )
        this.login_container = CTElement.create("div").classes("auth-container").append(
            CTElement.create("h2").classes("auth-title").i18n("auth.title"),
            this.form,
            this.button
        )
        this.processing_loading = CTSVG.loading.classes("ani").style("display", "none");
        this.processing_success = CTSVG.loaded_success.classes("suc").style("display", "none");
        this.processing_container = CTElement.create("div").classes("auth-container").classes("processing").append(
            this.processing_loading,
            this.processing_success
        )
        var inputs = [
            this.username,
            this.password
        ]
        for (const { input, box } of [
            { input: this.username, box: this.box_username },
            { input: this.password, box: this.box_password }
        ]) {
            input.listener("focus", () => {
                box.classes("active")
            }).listener("blur", () => {
                box.removeClasses("active")
            }).listener("keydown", (event) => {
                if (event.key == "Enter") {
                    // find empty input
                    for (const input of inputs) {
                        if (input.inputValue.trim().length == 0) {
                            input.focus()
                            return;
                        }
                    }
                    this.button.click()
                }
            })
        }

        super.append(this.login_container)

        app.style.addThemes('dark', {
            'auth-background-color': 'rgba(56, 56, 56, .8)',
        })
        app.style.addThemes('light', {
            'auth-background-color': 'rgba(255, 255, 255, .8)',
        })

        app.style.addStyles({
            ".auth-page": {
                "width": "100%",
                "height": "100%",
                "display": "flex",
                "justify-content": "center",
                "align-items": "center",
                "color": "var(--color)",
                "background": "var(--background)"
            },
            ".auth-container": {
                "min-width": "400px",
                "min-height": "256px",
                "border-radius": "10px",
                "background-color": "var(--auth-background-color)",
                "border": "1px solid var(--border-color)",
                "padding": "24px",
                "box-shadow": "0 0 10px var(--box-shadow)",
                "transition": "min-width var(--transition), min-height var(--transition)",
            },
            ".auth-input": {
                "background": "transparent",
                "outline": "none",
                "width": "100%",
                "height": "100%",
                "font-size": "0.875rem",
                "border": "none",
                "padding": "0 4px 0 4px",
                "transition": "border-color var(--transition)",
                "color": "inherit"
            },
            ".auth-form": {
                "display": "flex",
                "flex-direction": "column",
                "gap": "15px",
                "margin-top": "20px",
                "margin-bottom": "20px",
            },
            ".auth-input-box": {
                "padding": "5px",
                "height": "2.5rem",
                "border": "1px solid var(--border-color)",
                "border-radius": "4px",
                "transition": "border-color var(--transition), padding var(--transition)",
            },
            ".auth-input-box:hover": {
                "border": "1px solid var(--main-color)",
            },
            ".auth-input-box.active": {
                "border": "1px solid var(--main-color)",
                "box-shadow": "0 0 1px var(--main-color)",
            },
            ".auth-button": {
                "width": "100%",
                "height": "2.5rem",
                "border": "none",
                "border-radius": "4px",
                "background-color": "var(--main-color)",
                "color": "var(--dark-color)",
                "font-size": "0.875rem",
                "cursor": "pointer",
            },
            "@media (max-width: 600px)": {
                ".auth-container": {
                    "min-width": "100%",
                }
            },
            ".auth-container.processing": {
                "display": "flex",
                "flex-direction": "column",
                "justify-content": "center",
                "align-items": "center",
            },
            ".auth-container.processing svg": {
                "fill": "var(--main-color)",
                "margin": "auto",
                "display": "block",
                "width": "auto",
                "height": "96px",
            },
            ".auth-container.processing svg.suc": {
                "fill": "rgba(0, 250, 0, 0.8)",
            },
            ".auth-container.processing svg.ani": {
                "animation": "auth-spin 1s linear infinite",
            },
            "@keyframes auth-spin": {
                "0%": {
                    "transform": "rotate(0deg)"
                },
                "100%": {
                    "transform": "rotate(360deg)"
                }
            }
        })

        // add router
        app.addRoute("/auth/login", () => {
            authPage.render();
        })

        app.router.beforeHandler(() => {
            body.removeChild(this)
        })
    }
    render() {
        body.clear()
        body.append(this);
    }
}
class Application extends CTElement {
    constructor() {
        super("div").classes("application");

        this.menu = new CTMenu({
            width: '220px',
            transition: 'var(--transition)',
        });
        this.container = CTElement.create("div").classes("application-container")

        this.menuButton = CTElement.create("div").append(
            CTSVG.menu.listener(
                "click", () => {
                    this.menu.toggle();
                }
            )
        )

        super.append(this.menu, this.container);

        app.style.addStyles({
            ".application": {
                "height": "100%",
                "overflow": "hidden",
            },
            ".application-container": {
                "width": "100%",
                "transition": "margin-left var(--transition), width var(--transition)",
                "padding": "0 24px 24px 0",
            },
            ".ct-menu ~ .application-container": {
                "margin-left": "220px",
                "width": "calc(100% - 220px)"
            },
            ".ct-menu.action ~ .application-container": {
                "margin-left": "0",
                "width": "100%"
            }
        })

        app.router.beforeHandler((event) => {
            if (event.currentRoute.startsWith("/auth")) {
                header_left.removeChild(this.menuButton)
                return;
            } 
            header_left.prepend(this.menuButton)
        })

        this.menu.add({
            icon: CTSVG.iconDashboard,
            key: "/dashboard",
            title: 'i18n:dashboard',
            defaultRoute: true
        })
        this.menu.add({
            icon: CTSVG.iconDashboard,
            key: "/config",
            title: 'i18n:config',
            children: [
                {
                    key: "/proxy",
                    title: 'i18n:system',
                },
            ]
        })

        this.stream = new TextEventStream(window.location.origin + "/api");
        this.stream.connect()

        this.initRoute();
    }
    initRoute() {
        app.router.beforeHandler(() => {
            this.container.clear()
        })
        app.addRoute("/dashboard", () => {
            this.container.append((new CTFlex({
                width: {
                    500: 1,
                    768: 2,
                },
            })).append(
                CTCard({
                    handler: (element) => {
                        element.append(...CTCardText({
                            title: "i18n:title.system.cpu",
                            value: CTElement.create("h2").text("a")
                        }))
                    }
                }),
                CTCard({
                    handler: (element) => {
                        element.append(...CTCardText({
                            title: "i18n:title.system.cpu",
                            value: CTElement.create("h2").text("a")
                        }))
                    }
                }),
                CTCard({
                    handler: (element) => {
                        element.append(...CTCardText({
                            title: "i18n:title.system.cpu",
                            value: CTElement.create("h2").text("a")
                        }))
                    }
                }),
                CTCard({
                    handler: (element) => {
                        element.append(...CTCardText({
                            title: "i18n:title.system.cpu",
                            value: CTElement.create("h2").text("a")
                        }))
                    }
                }),
            ))
        })
    }
}
const app = createApp();
const alerts = new CTAlert();
const authPage = new AuthPage();
const application = new Application();
const body = CTElement.create("div").classes("app");
const header_left = CTElement.create("div").classes("header-left").append(
    CTElement.create("h2").text(document.title)
)
const header_right = CTElement.create("div").classes("header-right")
function initStyle() {
    app.style.addStyles({
        "body": {
            "color": "var(--color)",
            "background-color": "var(--background)",
            "height": "100vh"
        },
        "::-webkit-scrollbar, html ::-webkit-scrollbar": {
            "width": "5px",
            "height": "5px",
            "border-radius": "10px"
        },
        "::-webkit-scrollbar-thumb, html ::-webkit-scrollbar-thumb": {
            "box-shadow": "rgba(0, 0, 0, 0) 0px 0px 6px inset",
            "background-color": "rgb(102, 102, 102)",
            "border-radius": "10px"
        },
        "header": {
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100%",
            "height": "3.5rem",
            "background-color": "var(--background)",
            "z-index": "99999",
            "display": "flex",
            "justify-content": "space-between",
            "padding": "8px 12px",
        },
        "header svg": {
            "fill": "var(--color)",
            "height": "100%",
            "width": "100%",
            "cursor": "pointer"
        },
        ".header-left, .header-right": {
            "width": "auto",
            "height": "100%",
            "display": "flex",
            "align-items": "center"
        },
        ".container": {
            "display": "flex",
            "flex-flow": "column",
            "justify-content": "space-between",
            "height": "100vh",
            "width": "100vw",
            "overflow-y": "auto"
        },
        ".app-container": {
            "top": "3.5rem",
            "position": "fixed",
            "height": "calc(100% - 3.5rem)",
        },
        ".app": {
            "height": "auto",
            "width": "100vw",
        }
    })
    app.style.addGlobals({
        'transition': '150ms cubic-bezier(0.4, 0, 0.2, 1)'
    })
    app.style.addThemes('dark', {
        'border-color': 'rgba(196, 196, 196, .257)',
        'box-shadow': 'rgba(0, 0, 0, .5)',
        "main-color": "rgb(244, 209, 180)",
        "card-bg-color": "rgb(35, 35, 35)",
        "text-color": "rgba(255, 255, 255, .5)"
    })
    app.style.addThemes('light', {
        'border-color': 'rgba(50, 50, 50, .257)',
        'box-shadow': 'rgba(50, 50, 50, .1)',
        "main-color": "rgb(15, 198, 194)",
        "card-bg-color": "rgb(255, 255, 255)",
        "text-color": "rgba(0, 0, 0, .5)"
    })

    // add switch theme button
    var moon = CTSVG.moon
    var sun = CTSVG.sun
    var mode = CTElement.create("div").append(
    )
    header_right.append(
        mode
    )
    if (app.style.isDark()) {
        mode.append(sun)
    } else {
        mode.append(moon)
    }
    mode.listener("click", () => {
        app.style.setTheme(app.style.isDark() ? 'light' : 'dark')
        if (!app.style.isDark()) {
            mode.removeChild(sun)
            mode.append(moon)
        } else {
            mode.removeChild(moon)
            mode.append(sun)
        }
    })
}

function init() {
    initStyle();

    const header = CTElement.create("header")
    header.append(header_left, header_right)

    app.i18n.setLang('zh-cn')

    app.body.append(CTElement.create("div").classes("container").append(
        header,
        CTElement.create("div").classes("app-container").append(
            body
        )
    ));
}


async function main() {
    init();
    app.router.beforeHandler((event) => {
        let found = body.findChild(application) != null;
        if (event.currentRoute.startsWith("/auth") && found) {
            body.removeChild(application);
            return;
        }
        if (found) return;
        body.append(application)
    })
    //if (!await checkAuth()) {
    //    app.route("/auth/login")
    //}
}

main();