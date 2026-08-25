export function renderBackground(
  context: CanvasRenderingContext2D,
  image: CanvasImageSource,
  width: number,
  height: number,
  color: string
): void {
  context.clearRect(0, 0, width, height)
  context.fillStyle = color
  context.fillRect(0, 0, width, height)
  context.drawImage(image, 0, 0, width, height)
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('无法读取抠图结果'))
    image.src = url
  })
}

export async function composeBackground(sourceUrl: string, color: string): Promise<Blob> {
  const image = await loadImage(sourceUrl)
  const canvas = document.createElement('canvas')
  canvas.width = image.naturalWidth
  canvas.height = image.naturalHeight
  const context = canvas.getContext('2d')
  if (!context) throw new Error('当前浏览器不支持图片合成')
  renderBackground(context, image, canvas.width, canvas.height, color)
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      blob => (blob ? resolve(blob) : reject(new Error('生成证件照失败'))),
      'image/png'
    )
  })
}
