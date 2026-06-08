/** @type {import('next').NextConfig} */
const nextConfig = {
  // Strict Mode를 끕니다. 우리 흐름에선 페이지 mount → EventSource 생성으로
  // 백엔드 graph_app.stream()이 시작되고, 첫 노드 실행 시점에 체크포인트에
  // 부분 state가 기록됩니다. Strict Mode의 즉시 cleanup이 1차 EventSource를
  // close → 2차 mount가 'state 이미 있음 → snapshot 한 방' 분기로 빠져서
  // 사용자는 단계별 진행을 못 보게 됩니다. (prod 동작과는 무관하게 dev만
  // 영향. 우리 useEffect들은 외부 부수효과 안전한 cleanup을 이미 갖추고
  // 있어 Strict Mode가 잡아줄 신규 버그는 없습니다.)
  reactStrictMode: false,
};
export default nextConfig;
