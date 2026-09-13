import { useEffect, useRef } from 'react';

const TWEET_URL = 'https://x.com/pettiboy_com/status/2099143505503526962';

export function LaunchTweet() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const render = () => {
      const twitter = (window as Window & {
        twttr?: { widgets?: { load: (element: HTMLElement) => void } };
      }).twttr;
      if (container.current) twitter?.widgets?.load(container.current);
    };
    let script = document.querySelector<HTMLScriptElement>('#twitter-widgets');
    if (!script) {
      script = document.createElement('script');
      script.id = 'twitter-widgets';
      script.src = 'https://platform.twitter.com/widgets.js';
      script.async = true;
      document.body.appendChild(script);
    }
    script.addEventListener('load', render);
    render();
    return () => script.removeEventListener('load', render);
  }, []);

  return (
    <section className="launch-tweet" aria-labelledby="launch-tweet-title">
      <div>
        <div className="eyebrow">OUT IN THE WORLD</div>
        <h3 id="launch-tweet-title">Join the launch.</h3>
        <p>Follow the story behind ETH Arcade and tell us what you’d build next.</p>
        <a className="key" href={TWEET_URL} target="_blank" rel="noopener noreferrer">View our launch on X <span aria-hidden>↗</span></a>
      </div>
      <div className="launch-tweet-embed" ref={container}>
        <blockquote className="twitter-tweet" data-theme="light" data-dnt="true">
          <a href={TWEET_URL}>Read the ETH Arcade launch post on X</a>
        </blockquote>
      </div>
    </section>
  );
}
