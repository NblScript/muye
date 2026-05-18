type EmptyProps = {
  description?: string
}

export default function Empty({ description = '暂无数据' }: EmptyProps) {
  return (
    <div className="empty-state">
      <span>{description}</span>
    </div>
  )
}
