export function ErrorState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="error" role="alert">
      <h2>{title}</h2>
      <p>{detail}</p>
      {import.meta.env.DEV ? (
        <p>
          先在仓库根目录启动 API：<code>python -m tcmkb_api</code>
          （默认 http://127.0.0.1:8000），再刷新本页。
        </p>
      ) : (
        <p>请刷新重试。若仍失败，稍后再打开这一页。</p>
      )}
    </div>
  );
}
