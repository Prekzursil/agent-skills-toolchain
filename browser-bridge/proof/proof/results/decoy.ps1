Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.Text = 'ESTATE-BROWSER-PROOF-FOREGROUND'
$form.Width = 480
$form.Height = 180
$form.TopMost = $true
$label = New-Object System.Windows.Forms.Label
$label.Dock = 'Fill'
$label.Text = "Proof decoy — keep this focused.`r`nAgent browser is driven without OS keystrokes."
$form.Controls.Add($label)
$form.Add_Shown({ $form.Activate(); $form.BringToFront() })
[System.Windows.Forms.Application]::Run($form)
