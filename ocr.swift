import AppKit
import Vision

guard CommandLine.arguments.count == 2,
      let image = NSImage(contentsOfFile: CommandLine.arguments[1]),
      let data = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: data),
      let cgImage = bitmap.cgImage else {
    fputs("无法读取图片\n", stderr)
    exit(1)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["zh-Hans", "en-US"]
request.usesLanguageCorrection = true
do {
    try VNImageRequestHandler(cgImage: cgImage).perform([request])
    for item in request.results ?? [] {
        if let text = item.topCandidates(1).first?.string {
            print(text)
        }
    }
} catch {
    fputs("本地文字识别失败：\(error)\n", stderr)
    exit(1)
}
