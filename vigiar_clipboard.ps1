# Vigia a área de transferência do Windows. Sempre que uma imagem nova entra nela
# (ex.: Win+Shift+S), salva como PNG na pasta indicada e escreve o caminho na saída.
param([Parameter(Mandatory)] [string] $Pasta)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -Namespace Clip -Name Win32 -MemberDefinition @'
[DllImport("user32.dll")] public static extern uint GetClipboardSequenceNumber();
'@

$ultimo = [Clip.Win32]::GetClipboardSequenceNumber()
while ($true) {
    Start-Sleep -Milliseconds 500
    $atual = [Clip.Win32]::GetClipboardSequenceNumber()
    if ($atual -eq $ultimo) { continue }
    $ultimo = $atual
    try {
        if (-not [System.Windows.Forms.Clipboard]::ContainsImage()) { continue }
        $imagem = [System.Windows.Forms.Clipboard]::GetImage()
        $nome = "captura-{0:yyyyMMdd-HHmmss-fff}.png" -f (Get-Date)
        $imagem.Save((Join-Path $Pasta $nome), [System.Drawing.Imaging.ImageFormat]::Png)
        $imagem.Dispose()
        [Console]::Out.WriteLine($nome)
        [Console]::Out.Flush()
    } catch {
        # A área de transferência pode estar ocupada por outro programa; tenta no próximo ciclo
        $ultimo = 0
    }
}
