import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CheckSheet } from './CheckSheet';

describe('unavailable knowledge is not an empty successful search', () => {
  it('explains load failure in plain language', () => {
    const html = renderToStaticMarkup(<CheckSheet open quote="原句" where="本集" t={1} claims={[]} claimsUnavailable onClose={() => {}} onListen={() => {}} onStash={() => {}} />);
    expect(html).toContain('这集的知识点暂时没能打开');
    expect(html).not.toContain('这段附近暂时没有收录主张');
  });
  it('keeps the genuine nearby-empty state separate', () => {
    const html = renderToStaticMarkup(<CheckSheet open quote="原句" where="本集" t={1} claims={[]} onClose={() => {}} onListen={() => {}} onStash={() => {}} />);
    expect(html).toContain('这段附近暂时没有收录主张');
    expect(html).not.toContain('这集的知识点暂时没能打开');
  });
});
