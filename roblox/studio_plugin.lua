-- Save this Script as a local Studio plugin. The importer stays in this place.

local HttpService = game:GetService("HttpService")
local ServerStorage = game:GetService("ServerStorage")
local Selection = game:GetService("Selection")
local ChangeHistoryService = game:GetService("ChangeHistoryService")

local SERVER = "http://127.0.0.1:8765"
local toolbar = plugin:CreateToolbar("Prompt2Particles")
local toggle = toolbar:CreateButton("Prompt2Particles", "Open Prompt2Particles", "")
toggle.ClickableWhenViewportHidden = true

local info = DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Float, false, false, 380, 380, 340, 380)
local widget = plugin:CreateDockWidgetPluginGuiAsync("Prompt2ParticlesPanel", info)
widget.Title = "Prompt2Particles"

local function add(className, properties, parent)
	local instance = Instance.new(className)
	for name, value in pairs(properties) do
		instance[name] = value
	end
	instance.Parent = parent
	return instance
end

local function round(instance, radius)
	add("UICorner", { CornerRadius = UDim.new(0, radius) }, instance)
end

local colors = {
	background = Color3.fromRGB(28, 30, 35),
	field = Color3.fromRGB(43, 46, 52),
	button = Color3.fromRGB(52, 56, 63),
	primary = Color3.fromRGB(72, 113, 177),
	text = Color3.fromRGB(242, 244, 247),
	muted = Color3.fromRGB(171, 178, 188),
	error = Color3.fromRGB(244, 153, 153),
}

local panel = add("Frame", {
	Size = UDim2.fromScale(1, 1),
	BackgroundColor3 = colors.background,
	BorderSizePixel = 0,
}, widget)

add("TextLabel", {
	Position = UDim2.fromOffset(16, 16),
	Size = UDim2.new(1, -32, 0, 27),
	BackgroundTransparency = 1,
	Text = "Prompt2Particles",
	TextColor3 = colors.text,
	TextXAlignment = Enum.TextXAlignment.Left,
	TextSize = 21,
	Font = Enum.Font.SourceSansSemibold,
}, panel)

add("TextLabel", {
	Position = UDim2.fromOffset(16, 45),
	Size = UDim2.new(1, -32, 0, 18),
	BackgroundTransparency = 1,
	Text = "Describe an effect to create in Studio.",
	TextColor3 = colors.muted,
	TextXAlignment = Enum.TextXAlignment.Left,
	TextSize = 13,
	Font = Enum.Font.SourceSans,
}, panel)

add("Frame", {
	Position = UDim2.fromOffset(16, 76),
	Size = UDim2.new(1, -32, 0, 1),
	BackgroundColor3 = Color3.fromRGB(55, 59, 66),
	BorderSizePixel = 0,
}, panel)

add("TextLabel", {
	Position = UDim2.fromOffset(16, 89),
	Size = UDim2.new(1, -32, 0, 18),
	BackgroundTransparency = 1,
	Text = "Description",
	TextColor3 = colors.text,
	TextXAlignment = Enum.TextXAlignment.Left,
	TextSize = 14,
	Font = Enum.Font.SourceSansSemibold,
}, panel)

local promptBox = add("TextBox", {
	Position = UDim2.fromOffset(16, 112),
	Size = UDim2.new(1, -32, 0, 82),
	BackgroundColor3 = colors.field,
	BorderSizePixel = 0,
	ClearTextOnFocus = false,
	MultiLine = true,
	TextWrapped = true,
	TextXAlignment = Enum.TextXAlignment.Left,
	TextYAlignment = Enum.TextYAlignment.Top,
	TextColor3 = colors.text,
	PlaceholderColor3 = colors.muted,
	PlaceholderText = "Describe the particle effect...",
	Text = "",
	TextSize = 15,
	Font = Enum.Font.SourceSans,
}, panel)
round(promptBox, 7)
add("UIPadding", {
	PaddingTop = UDim.new(0, 9),
	PaddingBottom = UDim.new(0, 9),
	PaddingLeft = UDim.new(0, 11),
	PaddingRight = UDim.new(0, 11),
}, promptBox)
add("UIStroke", {
	Color = Color3.fromRGB(83, 89, 99),
	Transparency = 0.55,
	Thickness = 1,
}, promptBox)

local createButton = add("TextButton", {
	Position = UDim2.fromOffset(16, 206),
	Size = UDim2.new(1, -32, 0, 40),
	BackgroundColor3 = colors.primary,
	BorderSizePixel = 0,
	Text = "Create emitter",
	TextColor3 = colors.text,
	TextSize = 16,
	Font = Enum.Font.SourceSansSemibold,
}, panel)
round(createButton, 7)

local emitButton = add("TextButton", {
	Position = UDim2.fromOffset(16, 256),
	Size = UDim2.new(0.5, -21, 0, 34),
	BackgroundColor3 = colors.button,
	BorderSizePixel = 0,
	Text = "Emit",
	TextColor3 = colors.text,
	TextSize = 15,
	Font = Enum.Font.SourceSansSemibold,
}, panel)
round(emitButton, 7)

local focusButton = add("TextButton", {
	Position = UDim2.new(0.5, 5, 0, 256),
	Size = UDim2.new(0.5, -21, 0, 34),
	BackgroundColor3 = colors.button,
	BorderSizePixel = 0,
	Text = "Focus",
	TextColor3 = colors.text,
	TextSize = 15,
	Font = Enum.Font.SourceSansSemibold,
}, panel)
round(focusButton, 7)

local status = add("TextLabel", {
	Position = UDim2.fromOffset(16, 302),
	Size = UDim2.new(1, -32, 0, 32),
	BackgroundTransparency = 1,
	Text = "Start the local server, then create an emitter.",
	TextColor3 = colors.muted,
	TextXAlignment = Enum.TextXAlignment.Left,
	TextYAlignment = Enum.TextYAlignment.Top,
	TextWrapped = true,
	TextSize = 13,
	Font = Enum.Font.SourceSans,
}, panel)

local busy = false
local lastEmitter = nil
local lastAnchor = nil

local function setStatus(message, isError)
	status.Text = message
	status.TextColor3 = isError and colors.error or colors.muted
end

local function getImporter()
	local folder = ServerStorage:FindFirstChild("Prompt2Particles")
	local module = folder and folder:FindFirstChild("Importer")
	assert(module and module:IsA("ModuleScript"), "ServerStorage.Prompt2Particles.Importer is missing")
	return require(module)
end

local function post(path, body)
	local response = HttpService:RequestAsync({
		Url = SERVER .. path,
		Method = "POST",
		Headers = { ["Content-Type"] = "application/json" },
		Body = HttpService:JSONEncode(body),
	})
	if not response.Success then
		local message = "Server returned " .. tostring(response.StatusCode)
		local ok, decoded = pcall(HttpService.JSONDecode, HttpService, response.Body)
		if ok and type(decoded) == "table" and type(decoded.error) == "string" then
			message = decoded.error
		end
		error(message)
	end
	return HttpService:JSONDecode(response.Body)
end

local function focus(anchor)
	local camera = assert(workspace.CurrentCamera, "Studio camera is unavailable")
	local target = anchor.Position + Vector3.new(0, 2, 0)
	local distance = 16
	local attachment = anchor:FindFirstChildWhichIsA("Attachment")
	local emitter = attachment and attachment:FindFirstChildWhichIsA("ParticleEmitter")
	if emitter then
		for _, point in emitter.Size.Keypoints do
			distance = math.max(distance, point.Value * 5)
		end
	end
	distance = math.min(distance, 60)
	camera.CFrame = CFrame.lookAt(target + Vector3.new(0, distance * 0.25, distance), target)
	camera.Focus = CFrame.new(target)
end

local function previewPosition(index)
	local baseplate = assert(workspace:FindFirstChild("Baseplate"), "Workspace.Baseplate is missing")
	local top = baseplate.Position.Y + baseplate.Size.Y / 2
	local column = index % 8 - 3.5
	local row = math.floor(index / 8)
	return Vector3.new(
		baseplate.Position.X + column * 24,
		top + 2,
		baseplate.Position.Z + baseplate.Size.Z * 0.36 + row * 24
	)
end

local function placeRecord(record, Importer)
	local attachment, report = Importer.deserialize(record)
	assert(attachment, table.concat(report.errors, " | "))
	local emitter = attachment:FindFirstChild(record.emitter.name)
	if not emitter or not emitter:IsA("ParticleEmitter") then
		attachment:Destroy()
		error("imported record has no ParticleEmitter")
	end
	local recording = ChangeHistoryService:TryBeginRecording("GenerateParticle", "Generate particle")
	if not recording then
		attachment:Destroy()
		error("Studio could not start an undo recording")
	end
	local anchor
	local ok, failure = pcall(function()
		local folder = workspace:FindFirstChild("Prompt2ParticlesGenerated")
		if not folder then
			folder = Instance.new("Folder")
			folder.Name = "Prompt2ParticlesGenerated"
			folder.Parent = workspace
		end
		local index = #folder:GetChildren()
		anchor = Instance.new("Part")
		anchor.Name = string.format("Generated_%03d", index + 1)
		anchor.Anchored = true
		anchor.CanCollide = false
		anchor.CanTouch = false
		anchor.CanQuery = false
		anchor.Transparency = 1
		anchor.Size = Vector3.new(1, 1, 1)
		anchor.Position = previewPosition(index)
		attachment.Parent = anchor
		anchor.Parent = folder
	end)
	ChangeHistoryService:FinishRecording(recording, ok and Enum.FinishRecordingOperation.Commit or Enum.FinishRecordingOperation.Cancel)
	if not ok then
		attachment:Destroy()
		error(failure)
	end
	Selection:Set({ anchor })
	focus(anchor)
	return anchor, emitter, Importer.emit(emitter)
end

createButton.MouseButton1Click:Connect(function()
	if busy then return end
	local prompt = promptBox.Text:match("^%s*(.-)%s*$")
	if #prompt == 0 then
		setStatus("Enter a description first.", true)
		return
	end
	busy = true
	createButton.Text = "Creating..."
	setStatus("Running the model...")
	task.spawn(function()
		local ok, anchor, emitter, count = pcall(function()
			local Importer = getImporter()
			local response = post("/predict", { prompt = prompt })
			assert(type(response.record) == "table", "server sent no emitter")
			return placeRecord(response.record, Importer)
		end)
		busy = false
		createButton.Text = "Create emitter"
		if ok then
			lastAnchor, lastEmitter = anchor, emitter
			setStatus(count > 0 and ("Placed burst. Emitted " .. count .. ".") or "Placed continuous effect.")
		else
			setStatus(tostring(anchor) .. " Check the server window.", true)
		end
	end)
end)

emitButton.MouseButton1Click:Connect(function()
	if not lastEmitter or not lastEmitter.Parent then
		setStatus("Create an emitter first.", true)
		return
	end
	local count = getImporter().emit(lastEmitter)
	if count == 0 then
		count = math.max(1, math.floor(lastEmitter.Rate + 0.5))
		lastEmitter:Emit(count)
	end
	setStatus("Emitted " .. count .. " preview particles.")
end)

focusButton.MouseButton1Click:Connect(function()
	if not lastAnchor or not lastAnchor.Parent then
		setStatus("Create an emitter first.", true)
		return
	end
	focus(lastAnchor)
end)

toggle.Click:Connect(function()
	widget.Enabled = not widget.Enabled
end)
