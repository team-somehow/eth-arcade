import { Nav, Footer } from './sections/Chrome';
import { Film } from './sections/Film';
import { Demo } from './sections/Demo';
import { SDK } from './sections/SDK';
import { Proof, SponsorStrip } from './sections/Proof';
import { Reserve } from './sections/Reserve';

export default function App() {
  return (
    <>
      <div className="grain" aria-hidden />
      <Nav />
      <main>
      <Film />
      <div className="manifesto"><span>Less scrolling.</span><span>More <i>feeling.</i></span><p>A real knob. A moving market. A little room for play.</p></div>
      <section className="launch-section" id="launch" aria-labelledby="launch-title">
        <div className="eyebrow">THE LAUNCH FILM</div>
        <h2 id="launch-title">Watch our launch.</h2>
        <p>Meet the handheld, see Box Run in action, and discover what you can build.</p>
        <div className="launch-player">
          <iframe
            src="https://www.youtube-nocookie.com/embed/lb2-5xYZx_U"
            title="ETH Arcade launch video"
            loading="lazy"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            referrerPolicy="strict-origin-when-cross-origin"
            allowFullScreen
          />
        </div>
      </section>
      <SponsorStrip />
      <Demo />
      <SDK />
      <Proof />
      <Reserve />
      </main>
      <Footer />
    </>
  );
}
