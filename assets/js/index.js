import {
    Configuration,
    Element,
    ElementManager,
    Style,
    I18NManager,
    Router,
    createElement,
    SVGContainers,
    User,
    Modal,
    InputElement,
    Utils,
    calcElementHeight
} from './common.js'

const $configuration = new Configuration();
const $ElementManager = new ElementManager();
const $style = new Style($configuration);
const $i18n = new I18NManager();
const $router = new Router("/");
const $modal = new Modal();
const $title = document.title
$i18n.addLanguageTable("zh_CN", {
    "footer.powered_by": "由 %name% 提供服务支持",
})
$style.setTheme("light", {
    "main-color-r": "15",
    "main-color-g": "198",
    "main-color-b": "194",
    "main-color": "rgb(15, 198, 194)",
    "main-light-color": "rgb(23, 231, 229)",
    "color": "#000000",
    "dark-color": "#FFFFFF",
    "background": "#F5F6F8",
    "footer-background": "#F0F0F0",
    "background-hover": "#F0F1F3",
    "main-dark-color": "rgb(10, 157, 220)",
    "main-shadow-0-2-color": "rgba(15, 198, 194, 0.2)",
    "main-shadow-0-1-color": "rgba(15, 198, 194, 0.1)",
    "main-button-hover": "rgb(10, 138, 135)",
})
$style.setTheme("dark", {
    "main-color-r": "244",
    "main-color-g": "209",
    "main-color-b": "180",
    "main-color": "rgb(244, 209, 180)",
    "main-light-color": "rgb(255, 239, 210)",
    "color": "#ffffff",
    "dark-color": "#000000",
    "background": "#181818",
    "footer-background": "#202020",
    "background-hover": "#202020",
    "main-dark-color": "rgb(235, 187, 151)",
    "main-shadow-0-2-color": "rgba(244, 209, 180, 0.2)",
    "main-shadow-0-1-color": "rgba(244, 209, 180, 0.1)"
})
$style.addAll({
    "::-webkit-scrollbar, html ::-webkit-scrollbar": {
        "width": "5px",
        "height": "5px",
        "border-radius": "10px"
    },
    "::-webkit-scrollbar-thumb, html ::-webkit-scrollbar-thumb": {
        "box-shadow": "rgba(0, 0, 0, 0) 0px 0px 6px inset",
        "background-color": "rgb(102, 102, 102)",
        "border-radius": "10px",
    },
    "body": {
        "overflow": "hidden"
    },
    ".app": {
        "display": "flex",
        "flex-direction": "column",
        "flex-wrap": "nowrap",
        "justify-content": "space-between",
        "height": "100vh",
        "width": "100vw",
        "background": "var(--background)",
        "overflow-y": "auto",
        "color": "var(--color)"
    },
    "a": {
        "color": "var(--color)",
        "text-decoration": "none"
    },
    "a:hover": {
        "text-decoration": "underline"
    },
    "header": `
        background: var(--background);
        text-align: center;
        min-height: 56px;
        width: 100%;
        padding: 8px 8px 8px 8px;
        z-index: 1;
        display: flex;
        align-items: center;
        flex-wrap: nowrap;
        justify-content: space-between;
        color: var(--color);
        fill: var(--color);
    `,
    "header .content": {
        "display": "flex",
        "align-items": "center"
    },
    "header svg": {
        "width": "48px",
        "height": "48px",
        "padding": "8px", 
        "cursor": "pointer",
        "fill": "inherit"
    },
    "header .padding-left": {
        "padding-left": "8px",
    },
    "h1,h2,h3,h4,h5,h6,p": "margin:0;color:inherit",
    "svg": {
        "fill": "inherit"
    },
    "main": {
        "top": "56px",
        //"overflow": "auto"
    },
    "header.hidden": {
        "display": "none"
    },
    "header.hidden ~ main": {
        "top": "0px"
    },
    "footer": {
        "padding": "24px",
        "flex-direction": "column",
        "background": "var(--footer-background)",
        "color": "var(--color)",
        "display": "flex",
        "align-items": "center",
        "justify-content": "center"
    },
    "header .auth.disabled *": {
        "cursor": "not-allowed"
    },
})

class Menu extends Element {
    constructor() {
        super("div").classes("menu-side")
        $style.addAll({
            ".menu-side": {

            }
        })
    }
    toggle() {
        super.toggle("hidden")
    }
}

async function load() {
    const $dom_body = new Element(document.body);
    const $main = createElement("main")
    const $menu = new Menu();
    const $wrapper = createElement("wrapper").append(
        $menu,
        $main
    )

    const $app = createElement("div").classes("app")

    const $header = createElement("header")
    const $theme = {
        sun: SVGContainers.sun,
        moon: SVGContainers.moon
    }
    const $theme_change = createElement("div").append(
        $theme[$configuration.get("theme") == "light" ? "moon" : "sun"]
    )
    const $header_content_left = createElement("div").classes("content").append(
        SVGContainers.menu.addEventListener("click", () => {

        }),
        createElement("h3").text($title)
    );
    const $header_content_right = createElement("div").classes("content").append(
        $theme_change
    );
    const $footer = createElement("footer").append(
        createElement("p").i18n(
            "footer.powered_by"
        ).t18n({
            "name": createElement("a").text(
                "tianxiu2b2t"
            ).attributes({
                "href": "https://github.com/tianxiu2b2t",
                "target": "_blank"
            })
        })
    )

    globalThis.$app = $app;

    for (const $theme_key in $theme) {
        $theme[$theme_key].addEventListener("click", () => {
            $theme_change.removeChild($theme[$theme_key]);
            $style.applyTheme($theme_key == "sun" ? "light" : "dark");
            $theme_change.append($theme[$theme_key == "sun" ? "moon" : "sun"]);
            $configuration.set("theme", $theme_key == "sun" ? "light" : "dark");
        })
    }

    $header.append($header_content_left, $header_content_right);

    $app.append(
        createElement("container").append(
            $header,
            $main,
        ),
        $footer
    );

    $dom_body.appendBefore($app);

    $router.on("/", () => {
        $main.append(
            createElement("h1").append(createElement("span").text("哎哟喂！此页面还没有开发完成欸……")),
            createElement("h1").append(createElement("span").text("或许你可以拥抱一下我们的电脑老师？"))
        )
    })

    $router.before_handler(() => {
        $header.removeAllClasses()
        $main.getClasses
        while ($main.firstChild != null) {
            $main.removeChild($main.firstChild)
        }
    })
    
    $router.init()
    const observer = new ResizeObserver((..._) => {
        var header = calcElementHeight($header)
        var height = window.innerHeight - header
        $wrapper.style("height", "auto")
        var wrapper = calcElementHeight($wrapper)
        var height = Math.max(height, wrapper)
        $wrapper.style("height", `${height}px`)
    });
    observer.observe($app.origin, { childList: true, subtree: true });

}
window.addEventListener("DOMContentLoaded", async () => {
    await load()
    Array.from(document.getElementsByClassName("preloader")).forEach(e => {
        const element = new Element(e);
        requestAnimationFrame(() => {
            element.classes("hidden");
            setTimeout(() => {
                element.remove();
            }, 1000)
        })
    })
})
