# POLICY.md: 정책과 인사이트

담는 범위: 타겟팅 정책, 비용 가정, 민감도 분석, 세그먼트 규칙, Sleeping Dogs 점검.

결정 당시 기록이며 지금 규칙과 다를 수 있다. 결정한 날짜순으로 항목을 둔다.

## 2026-11-27 마진율은 40.25%로 고정하고, 메일 1통 비용 c는 0\~0.40달러 축으로 두어 2008년 이메일 단가와 우편요금을 참고 지점으로 표시한다

- 결정:
  - 마진율 m은 40.25%로 고정한다. 미국 Census 2009 Annual Retail Trade Survey의 2008년 매출총이익률 37.0%(NAICS 4541, Electronic shopping and mail-order houses)와 43.5%(NAICS 448, Clothing and clothing accessories stores)의 가운데 값이다. 배송·결제 같은 변동비를 빼지 않은 값이라 증분 이익 마진의 위쪽 한계로 보고한다.
  - 1통 비용 c는 정하지 않고 0\~0.40달러 축으로 둔다. 남성용 메일의 손익분기는 0.31달러(0.4025 × `spend` 효과 0.770)다.
  - 참고 지점은 둘이다. 2008년 이메일은 0.005\~0.010달러(MailChimp 2008-05 Wayback 보관 요금표의 선불 크레딧, 75,000통 750달러\~200,000통 1,000달러)다. 2008년 우편요금은 0.339달러(USPS 2008-05-12 Standard Mail flat 3.3oz 이하 5-Digit automation, 우편요금만)다. 우편 지점은 이메일에서 잰 효과가 우편에서도 같다고 가정한 비교점이다.
  - 수신 거부 손실은 넣지 않는다. 보고에는 빠진 비용으로 적는다.
- 근거: 사용자 지시(2026-11-27). 시점은 Hillstrom 데이터가 공개된 2008년에 맞췄다. `spend` 효과 0.770은 `artifacts/ANA-001/tables/ate.csv`다. 정책의 우열은 c/m으로 정해져 m을 하나로 고정해도 c 축이 같은 비율로 늘거나 줄 뿐이다. 마진 출처: https://www2.census.gov/programs-surveys/arts/tables/2009/2009_arts_tables.xls("Gross Margin as % of Sales" 시트). 단가 출처: https://web.archive.org/web/20080513191714/http://www.mailchimp.com/pricing.phtml, https://about.usps.com/postal-bulletin/2008/html/pb22247/html/not123_020.html
- 기각한 대안: 월 구독 요금(iContact 2008-12 보관본, 75,000명 월 529달러)을 발송 단가로 나누는 안. 구독 요금은 목록 크기로 매겨져 발송을 줄여도 줄지 않는다.
- 정본: 아직 없음. M3 실험 설정에 반영한다.
- 승인: 2026-11-27

