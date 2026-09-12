import { Nav, Footer } from './sections/Chrome';
import { Film } from './sections/Film';
import { Demo } from './sections/Demo';
import { Proof } from './sections/Proof';
import { Reserve } from './sections/Reserve';

export default function App() {
  return (
    <>
      <div className="grain" aria-hidden />
      <Nav />
      <Film />
      <Demo />
      <Proof />
      <Reserve />
      <Footer />
    </>
  );
}
