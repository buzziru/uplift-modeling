# tests 규약

## 테스트 도입 순서

| 시점 | 테스트 |
| --- | --- |
| 처음부터 | unit test, 지표 함수의 property-based test(`hypothesis`) |
| 첫 파이프라인이 돌 때 | integration test |
| 첫 uplift 추정량을 만들 때 | 효과를 미리 심은 합성 데이터에서 추정량이 그 효과를 되찾는지 보는 test |
| M2 최종 방법론과 금액 모델을 채택할 때 | regression test(기준값 파일과 허용 오차로 비교). 기준값 파일의 형식(고객별 처치와 결과를 어떻게 다룰지)도 이때 정한다 |
| 대시보드가 나온 뒤 | e2e test(Playwright) |
