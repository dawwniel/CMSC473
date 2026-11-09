-- Run from Studio's Command Bar or the MCP connector:
-- require(game.ServerStorage.Prompt2Particles.CIXReview).showPage("Particle", 1)
-- require(game.ServerStorage.Prompt2Particles.CIXReview).showPage("FlipBook", 1, true)

local Review = {}

local Workspace = game:GetService("Workspace")
local PluginGuiService = game:GetService("PluginGuiService")

local PER_PAGE = 12
local BOARD_POSITION = Vector3.new(0, 26, -900)
local CAMERA_POSITION = Vector3.new(0, 26, -855)

local function gallery(kind)
	assert(kind == "Particle" or kind == "FlipBook", "kind must be Particle or FlipBook")
	local root = PluginGuiService:FindFirstChild("CIX_Library")
	assert(root, "Open CIX Library in Studio first")
	return root.CIX_Library.Page[kind]
end

local function cards(kind)
	local found = {}
	for _, card in ipairs(gallery(kind):GetChildren()) do
		local image = card:FindFirstChildWhichIsA("ImageButton", true)
		if image then
			table.insert(found, { name = card.Name, image = image.Image })
		end
	end
	table.sort(found, function(a, b)
		return a.name < b.name
	end)
	return found
end

function Review.catalog()
	return { Particle = cards("Particle"), FlipBook = cards("FlipBook") }
end

local function clearBoard()
	local old = Workspace:FindFirstChild("CIXTextureReview")
	if old then
		old:Destroy()
	end
	local folder = Instance.new("Folder")
	folder.Name = "CIXTextureReview"
	folder.Parent = Workspace
	return folder
end

function Review.showPage(kind, pageNumber, lightBackground)
	local entries = cards(kind)
	pageNumber = pageNumber or 1
	local totalPages = math.ceil(#entries / PER_PAGE)
	assert(pageNumber >= 1 and pageNumber <= totalPages, "page out of range")

	local folder = clearBoard()
	folder:SetAttribute("Kind", kind)
	folder:SetAttribute("Page", pageNumber)
	folder:SetAttribute("TotalPages", totalPages)
	folder:SetAttribute("Background", lightBackground and "light" or "dark")

	local board = Instance.new("Part")
	board.Name = "Board"
	board.Anchored = true
	board.CanCollide = false
	board.Size = Vector3.new(48, 31, 0.25)
	board.Position = BOARD_POSITION
	board.Color = lightBackground and Color3.fromRGB(210, 213, 219) or Color3.fromRGB(19, 24, 33)
	board.Parent = folder

	local startIndex = (pageNumber - 1) * PER_PAGE + 1
	for i = 1, math.min(PER_PAGE, #entries - startIndex + 1) do
		local entry = entries[startIndex + i - 1]
		local column = (i - 1) % 4
		local row = math.floor((i - 1) / 4)
		local part = Instance.new("Part")
		part.Name = string.format("%02d_%s", startIndex + i - 1, entry.name)
		part.Anchored = true
		part.CanCollide = false
		part.Size = Vector3.new(10.5, 8.8, 0.15)
		part.Position = BOARD_POSITION + Vector3.new((column - 1.5) * 11.7, (1 - row) * 9.8, 0.4)
		part.Color = lightBackground and Color3.fromRGB(245, 245, 245) or Color3.fromRGB(38, 43, 53)
		part:SetAttribute("CIXName", entry.name)
		part:SetAttribute("CIXKind", kind)
		part:SetAttribute("CIXImage", entry.image)
		part.Parent = folder

		local decal = Instance.new("Decal")
		decal.Name = "Image"
		decal.Face = Enum.NormalId.Back
		decal.Texture = entry.image
		decal.Parent = part
	end

	local camera = Workspace.CurrentCamera
	camera.CameraType = Enum.CameraType.Scriptable
	camera.CFrame = CFrame.lookAt(CAMERA_POSITION, BOARD_POSITION)
	camera.FieldOfView = 58
	return entries, totalPages
end

function Review.showNames(kind, names, lightBackground)
	assert(#names <= PER_PAGE, "showNames accepts at most 12 names")
	local all = cards(kind)
	local byName = {}
	for _, entry in ipairs(all) do
		byName[entry.name] = entry
	end
	local folder = clearBoard()
	local board = Instance.new("Part")
	board.Name = "Board"
	board.Anchored = true
	board.CanCollide = false
	board.Size = Vector3.new(48, 31, 0.25)
	board.Position = BOARD_POSITION
	board.Color = lightBackground and Color3.fromRGB(210, 213, 219) or Color3.fromRGB(19, 24, 33)
	board.Parent = folder
	for i, name in ipairs(names) do
		local entry = assert(byName[name], "CIX entry not found: " .. name)
		local column = (i - 1) % 4
		local row = math.floor((i - 1) / 4)
		local part = Instance.new("Part")
		part.Name = string.format("%02d_%s", i, name)
		part.Anchored = true
		part.CanCollide = false
		part.Size = Vector3.new(10.5, 8.8, 0.15)
		part.Position = BOARD_POSITION + Vector3.new((column - 1.5) * 11.7, (1 - row) * 9.8, 0.4)
		part.Color = lightBackground and Color3.fromRGB(245, 245, 245) or Color3.fromRGB(38, 43, 53)
		part:SetAttribute("CIXName", name)
		part:SetAttribute("CIXKind", kind)
		part:SetAttribute("CIXImage", entry.image)
		part.Parent = folder
		local decal = Instance.new("Decal")
		decal.Name = "Image"
		decal.Face = Enum.NormalId.Back
		decal.Texture = entry.image
		decal.Parent = part
	end
	local camera = Workspace.CurrentCamera
	camera.CameraType = Enum.CameraType.Scriptable
	camera.CFrame = CFrame.lookAt(CAMERA_POSITION, BOARD_POSITION)
	camera.FieldOfView = 58
	return folder
end

return Review
