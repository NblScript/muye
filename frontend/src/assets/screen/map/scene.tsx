import { Suspense } from 'react'
import type { ScreenViewModel } from '../model'
import Bottom from './bottom'
import Cloud from './cloud'
import Field from './field'

export default function Scene({ model }: { model: ScreenViewModel }) {
  return (
    <Suspense fallback={null}>
      <Cloud />
      <Field model={model} />
      <Bottom />
    </Suspense>
  )
}
