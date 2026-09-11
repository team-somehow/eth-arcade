import { Nav, Footer } from './sections/Chrome';
import { Film } from './sections/Film';
import { Demo } from './sections/Demo';
import { Reserve } from './sections/Reserve';

export default function App() {
  return (
    <>
      <div className="grain" aria-hidden />
      <Nav />
      <Film />
      <Demo />
      <Reserve />
      <Footer />
    </>
  );
}
