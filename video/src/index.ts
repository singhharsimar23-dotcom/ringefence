import {continueRender, delayRender, registerRoot, staticFile} from "remotion";
import {Root} from "./Root";

// Geist must be loaded before any frame is captured, or the first frames render in a fallback font.
const h = delayRender("fonts");
Promise.all([
  new FontFace("Geist", `url(${staticFile("fonts/Geist-Variable.woff2")}) format("woff2")`, {weight: "100 900"}).load(),
  new FontFace("Geist Mono", `url(${staticFile("fonts/GeistMono-Variable.woff2")}) format("woff2")`, {weight: "100 900"}).load(),
]).then((fs) => {
  fs.forEach((x) => document.fonts.add(x));
  continueRender(h);
});

registerRoot(Root);
