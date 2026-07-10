import { readdir, readFile, stat } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url))
const assetsDirectory = path.resolve(scriptDirectory, '../../../static/assets')
const maximumHomePageBytes = 500 * 1024
const requiredLazyChunkPrefixes = [
  'TaskPanel-',
  'MarketReviewReportView-',
  'StockHistoryTrendDrawer-',
  'ReportSummary-',
  'ReportMarkdownDrawer-',
  'RunFlowPanel-',
]

const assetNames = await readdir(assetsDirectory)
const homePageNames = assetNames.filter((name) => /^HomePage-[\w-]+\.js$/.test(name))

if (homePageNames.length === 0) {
  throw new Error(`No HomePage bundle found in ${assetsDirectory}. Run npm run build first.`)
}

const candidates = await Promise.all(
  homePageNames.map(async (name) => {
    const filePath = path.join(assetsDirectory, name)
    const metadata = await stat(filePath)
    return { name, filePath, size: metadata.size, modifiedAt: metadata.mtimeMs }
  }),
)
const latest = candidates.sort((left, right) => right.modifiedAt - left.modifiedAt)[0]
const source = await readFile(latest.filePath, 'utf8')
const missingLazyChunks = requiredLazyChunkPrefixes.filter((prefix) => !source.includes(prefix))

if (latest.size > maximumHomePageBytes) {
  throw new Error(
    `${latest.name} is ${(latest.size / 1024).toFixed(2)} KiB; V92 limit is ${(maximumHomePageBytes / 1024).toFixed(0)} KiB.`,
  )
}

if (missingLazyChunks.length > 0) {
  throw new Error(`HomePage does not lazy-load required feature chunks: ${missingLazyChunks.join(', ')}`)
}

console.log(
  `DSA_HOMEPAGE_BUNDLE_V92_OK file=${latest.name} size_kib=${(latest.size / 1024).toFixed(2)} lazy_chunks=${requiredLazyChunkPrefixes.length}`,
)
