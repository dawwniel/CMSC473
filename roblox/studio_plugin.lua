-- Save this Script as a local Studio plugin. The importer stays in this place.

local HttpService = game:GetService("HttpService")
local ServerStorage = game:GetService("ServerStorage")
local Selection = game:GetService("Selection")
local ChangeHistoryService = game:GetService("ChangeHistoryService")

local SERVER = "http://127.0.0.1:8765"
local toolbar = plugin:CreateToolbar("Prompt2Particles")
local toggle = toolbar:CreateButton("Prompt2Particles", "Open particle panel", "")
toggle.ClickableWhenViewportHidden = true

local info = DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Float, false, false, 360, 322, 330, 322)
local widget = plugin:CreateDockWidgetPluginGuiAsync("Prompt2ParticlesPanel", info)
widget.Title = "Particles"

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

local panel = add("Frame", {
	Size = UDim2.fromScale(1, 1),
	BackgroundColor3 = Color3.fromRGB(34, 36, 40),
	BorderSizePixel = 0,
}, widget)

add("TextLabel", {
	Position = UDim2.fromOffset(16, 12),
	Size = UDim2.new(1, -126, 0, 24),
	BackgroundTransparency = 1,
	Text = "New particle",
	TextColor3 = Color3.fromRGB(235, 237, 240),
	TextXAlignment = Enum.TextXAlignment.Left,
	TextSize = 18,
	Font = Enum.Font.SourceSansSemibold,
}, panel)

local nextButton = add("TextButton", {
	Position = UDim2.new(1, -108, 0, 12),
	Size = UDim2.fromOffset(92, 24),
	BackgroundColor3 = Color3.fromRGB(48, 51, 56),
	BorderSizePixel = 0,
	Text = "Next test",
	TextColor3 = Color3.fromRGB(201, 206, 213),
	TextSize = 13,
	Font = Enum.Font.SourceSans,
}, panel)
round(nextButton, 4)

local promptBox = add("TextBox", {
	Position = UDim2.fromOffset(16, 44),
	Size = UDim2.new(1, -32, 0, 88),
	BackgroundColor3 = Color3.fromRGB(49, 52, 57),
	BorderSizePixel = 0,
	ClearTextOnFocus = false,
	MultiLine = true,
	TextWrapped = true,
	TextXAlignment = Enum.TextXAlignment.Left,
	TextYAlignment = Enum.TextYAlignment.Top,
	TextColor3 = Color3.fromRGB(240, 242, 245),
	PlaceholderText = "Small blue sparks that shoot outward and fade",
	Text = "",
	TextSize = 15,
	Font = Enum.Font.SourceSans,
}, panel)
round(promptBox, 5)

local createButton = add("TextButton", {
	Position = UDim2.fromOffset(16, 143),
	Size = UDim2.new(1, -32, 0, 36),
	BackgroundColor3 = Color3.fromRGB(58, 109, 177),
	BorderSizePixel = 0,
	Text = "Create emitter",
	TextColor3 = Color3.new(1, 1, 1),
	TextSize = 16,
	Font = Enum.Font.SourceSansSemibold,
}, panel)
round(createButton, 5)

local emitButton = add("TextButton", {
	Position = UDim2.fromOffset(16, 188),
	Size = UDim2.new(0.5, -22, 0, 30),
	BackgroundColor3 = Color3.fromRGB(62, 65, 70),
	BorderSizePixel = 0,
	Text = "Emit",
	TextColor3 = Color3.fromRGB(232, 234, 237),
	TextSize = 15,
	Font = Enum.Font.SourceSansSemibold,
}, panel)
round(emitButton, 4)

local focusButton = add("TextButton", {
	Position = UDim2.new(0.5, 6, 0, 188),
	Size = UDim2.new(0.5, -22, 0, 30),
	BackgroundColor3 = Color3.fromRGB(62, 65, 70),
	BorderSizePixel = 0,
	Text = "Focus",
	TextColor3 = Color3.fromRGB(232, 234, 237),
	TextSize = 15,
	Font = Enum.Font.SourceSansSemibold,
}, panel)
round(focusButton, 4)

local status = add("TextLabel", {
	Position = UDim2.fromOffset(16, 226),
	Size = UDim2.new(1, -32, 0, 29),
	BackgroundTransparency = 1,
	Text = "Start the local server, then create an emitter.",
	TextColor3 = Color3.fromRGB(178, 184, 193),
	TextXAlignment = Enum.TextXAlignment.Left,
	TextYAlignment = Enum.TextYAlignment.Top,
	TextWrapped = true,
	TextSize = 13,
	Font = Enum.Font.SourceSans,
}, panel)

add("TextLabel", {
	Position = UDim2.fromOffset(16, 260),
	Size = UDim2.new(1, -32, 0, 18),
	BackgroundTransparency = 1,
	Text = "How did it look?",
	TextColor3 = Color3.fromRGB(151, 158, 168),
	TextXAlignment = Enum.TextXAlignment.Left,
	TextSize = 13,
	Font = Enum.Font.SourceSans,
}, panel)

local feedbackFrame = add("Frame", {
	Position = UDim2.fromOffset(16, 284),
	Size = UDim2.new(1, -32, 0, 24),
	BackgroundTransparency = 1,
}, panel)

local feedbackLabels = {
	{ "Good", "good" },
	{ "Texture", "texture" },
	{ "Motion", "motion" },
	{ "Other", "other" },
}
local feedbackButtons = {}
for i, item in ipairs(feedbackLabels) do
	local button = add("TextButton", {
		Position = UDim2.new((i - 1) / 4, i == 1 and 0 or 4, 0, 0),
		Size = UDim2.new(0.25, i == 1 and -3 or -4, 0, 24),
		BackgroundColor3 = Color3.fromRGB(48, 51, 56),
		BorderSizePixel = 0,
		Text = item[1],
		TextColor3 = Color3.fromRGB(201, 206, 213),
		TextSize = 13,
		Font = Enum.Font.SourceSans,
	}, feedbackFrame)
	round(button, 4)
	feedbackButtons[item[2]] = button
end

local busy = false
local lastEmitter = nil
local lastAnchor = nil
local lastRequestId = nil

local function setStatus(message, isError)
	status.Text = message
	status.TextColor3 = isError and Color3.fromRGB(241, 145, 145) or Color3.fromRGB(178, 184, 193)
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

nextButton.MouseButton1Click:Connect(function()
	task.spawn(function()
		local ok, result = pcall(function()
			local response = HttpService:RequestAsync({ Url = SERVER .. "/next_prompt", Method = "GET" })
			assert(response.Success, "local server is unavailable")
			return HttpService:JSONDecode(response.Body)
		end)
		if ok and type(result.prompt) == "string" then
			promptBox.Text = result.prompt
			setStatus(string.format("Test prompt %d/%d: %s", result.number, result.total, result.category))
		else
			setStatus("Could not load a test prompt. Start the local server.", true)
		end
	end)
end)

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
		local ok, anchor, emitter, count, requestId = pcall(function()
			local Importer = getImporter()
			local response = post("/predict", { prompt = prompt })
			assert(type(response.record) == "table", "server sent no emitter")
			local part, result, emitted = placeRecord(response.record, Importer)
			return part, result, emitted, response.request_id
		end)
		busy = false
		createButton.Text = "Create emitter"
		if ok then
			lastAnchor, lastEmitter, lastRequestId = anchor, emitter, requestId
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

for rating, button in pairs(feedbackButtons) do
	button.MouseButton1Click:Connect(function()
		if not lastRequestId then
			setStatus("Create an emitter before rating it.", true)
			return
		end
		local requestId = lastRequestId
		task.spawn(function()
			local ok, failure = pcall(function()
				post("/feedback", { request_id = requestId, rating = rating })
			end)
			setStatus(ok and "Feedback saved." or tostring(failure), not ok)
		end)
	end)
end

toggle.Click:Connect(function()
	widget.Enabled = not widget.Enabled
end)
