using System.Globalization;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.Formats;
using SixLabors.ImageSharp.Formats.Webp;
using SixLabors.ImageSharp.PixelFormats;

if (args.Length != 4)
    throw new ArgumentException("Usage: WebpConverter <input-directory> <output-directory> <quality> <method>");

var quality = int.Parse(args[2], CultureInfo.InvariantCulture);
var method = int.Parse(args[3], CultureInfo.InvariantCulture);
if (quality is < 0 or > 100 || method is < 0 or > 6)
    throw new ArgumentException("WebP quality must be 0–100 and method must be 0–6");

var files = Directory.GetFiles(args[0], "minecraft_texture_atlas-*.png")
    .OrderBy(path => path, StringComparer.Ordinal).ToArray();
if (files.Length == 0) throw new InvalidDataException("No atlas PNGs to convert");
Directory.CreateDirectory(args[1]);

var encoder = new WebpEncoder
{
    FileFormat = WebpFileFormatType.Lossless,
    NearLossless = false,
    TransparentColorMode = TransparentColorMode.Preserve,
    Quality = quality,
    Method = (WebpEncodingMethod)method,
    SkipMetadata = true
};

foreach (var file in files)
{
    var suffix = Path.GetFileNameWithoutExtension(file)["minecraft_texture_atlas-".Length..];
    if (!int.TryParse(suffix, NumberStyles.None, CultureInfo.InvariantCulture, out var page))
        throw new InvalidDataException($"Invalid atlas page: {file}");
    var output = Path.Combine(args[1], $"items-{page}.webp");
    using var source = Image.Load<Rgba32>(file);
    source.Save(output, encoder);

    // Decode the actual output and compare every RGBA pixel, including transparent
    // gutters. A failed conversion must never be published as a valid atlas.
    using var decoded = Image.Load<Rgba32>(output);
    if (decoded.Width != source.Width || decoded.Height != source.Height)
        throw new InvalidDataException($"WebP dimensions changed: {output}");
    source.ProcessPixelRows(decoded, (original, converted) =>
    {
        for (var y = 0; y < original.Height; y++)
        {
            if (!original.GetRowSpan(y).SequenceEqual(converted.GetRowSpan(y)))
                throw new InvalidDataException($"WebP RGBA pixels changed: {output}, row {y}");
        }
    });
    Console.WriteLine($"Verified lossless WebP: items-{page}.webp ({new FileInfo(file).Length} -> {new FileInfo(output).Length} bytes)");
}
