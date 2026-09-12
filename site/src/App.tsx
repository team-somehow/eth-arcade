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
