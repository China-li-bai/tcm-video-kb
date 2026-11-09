import { getAllLectures } from "./lectures";
import { expect, it } from 'vitest';
import vectors from '../../../tests/fixtures/citation-links.json';
import { watchHrefFromCite } from '../panel/format';

it.each(vectors)('shared Python/frontend canonical seconds and identity $id / $t', (c) => {
  expect(watchHrefFromCite({ video_id:c.id, start_s:c.t as number|undefined, t_url:'https://evil.test' })).toBe(c.href);
});
it.each([NaN,Infinity,-Infinity])('nonfinite %s is not silently a beginning-of-lecture citation', (start_s) => {
  expect(watchHrefFromCite({video_id:'shl-001',start_s})).toBeNull();
});
it('unpublished transcript still has a real catalog watch target; an unknown lecture does not',()=>{
  expect(watchHrefFromCite({video_id:'zj-083',start_s:163.36})).toBe('/watch/zj-083?t=163');
  expect(watchHrefFromCite({video_id:'shl-999',start_s:163})).toBeNull();
  expect(watchHrefFromCite({t_url:'/watch/shl-001?t=20'})).toBeNull();
});

it('every actual catalog identity has a safe request link, independent of transcript coverage',()=>{
  for(const lecture of getAllLectures()) {
    expect(watchHrefFromCite({video_id:lecture.id,start_s:125.99})).toBe(`/watch/${lecture.id}?t=125`);
  }
});
