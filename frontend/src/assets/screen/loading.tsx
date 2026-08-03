import styled from 'styled-components'

const Wrapper = styled.div`
  position: fixed;
  inset: 0;
  z-index: 999;
  display: grid;
  place-items: center;
  background: #fff5e8;

  .loader {
    width: 48px;
    height: 48px;
    border: 4px solid rgba(196, 138, 42, 0.2);
    border-top-color: #c48a2a;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
`

const Text = styled.div`
  margin-top: 16px;
  color: #b8705a;
  font-size: 14px;
  letter-spacing: 2px;
`

export default function Loading() {
  return (
    <Wrapper>
      <div style={{ textAlign: 'center' }}>
        <div className="loader" />
        <Text>正在加载 3D 农田场景…</Text>
      </div>
    </Wrapper>
  )
}
