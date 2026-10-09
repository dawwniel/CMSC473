--[[
	Prompt2Particles exporter

	Turns Roblox particles into JSONL records (one JSON object per line, one
	line per ParticleEmitter) in the format roblox/importer.lua reads. The
	module only reads the place; it never changes anything.

	Records are routed by the "Split" attribute on each emitter's attachment.
	The caller writes each split's lines to src/data/<split>/particles_<split>.jsonl;
	splits in Exporter.EXCLUDED_SPLITS (currently "review") are skipped.

	Output is deterministic: object keys are sorted, numbers are rounded to
	Exporter.DECIMALS places, and records are ordered by id. Exporting the same
	place twice gives identical bytes.

	Main entry points:
	  Exporter.collect(root)                       -> sorted list of { id, emitter }
	  Exporter.serialize(emitter, root)            -> record, warnings
	  Exporter.encodeLine(record)                  -> one JSON line (no newline)
	  Exporter.exportBatch(root, offset, limit)    -> { lines, total, nextOffset, warnings }
	  Exporter.scan(root)                          -> counts and checks for the export report
]]

local Exporter = {}

Exporter.FORMAT_VERSION = 1
Exporter.DECIMALS = 6
Exporter.SPLIT_ATTRIBUTE = "Split"
Exporter.EXCLUDED_SPLITS = { review = true }
Exporter.PROMPT_NAME = "Prompt"

-- String attributes that hold JSON text; exported as {"_type":"JSONString","value":...}.
Exporter.JSON_ATTRIBUTES = { PromptAlternates = true }

-- Properties exported per class. A class missing here is still exported (name,
-- class, attributes, children) with a warning, so new content never breaks the export.
-- Attachment.Position/Orientation are left out because CFrame already holds them.
Exporter.PROPERTIES = {
	ParticleEmitter = {
		"Acceleration", "Brightness", "Color", "Drag", "EmissionDirection", "Enabled",
		"FlipbookFramerate", "FlipbookLayout", "FlipbookMode", "FlipbookStartRandom",
		"Lifetime", "LightEmission", "LightInfluence", "LockedToPart", "Orientation",
		"Rate", "RotSpeed", "Rotation", "Shape", "ShapeInOut", "ShapePartial", "ShapeStyle",
		"Size", "Speed", "SpreadAngle", "Squash", "Texture", "TimeScale", "Transparency",
		"VelocityInheritance", "WindAffectsDrag", "ZOffset",
	},
	Attachment = { "CFrame", "Visible" },
	BillboardGui = {
		"AlwaysOnTop", "Brightness", "ClipsDescendants", "Enabled", "ExtentsOffset",
		"LightInfluence", "MaxDistance", "Size", "SizeOffset", "StudsOffset",
		"StudsOffsetWorldSpace", "ZIndexBehavior",
	},
	TextLabel = {
		"AnchorPoint", "BackgroundColor3", "BackgroundTransparency", "BorderSizePixel",
		"FontFace", "Position", "RichText", "Size", "Text", "TextColor3", "TextScaled",
		"TextSize", "TextTransparency", "TextWrapped", "TextXAlignment", "TextYAlignment",
	},
	Folder = {},
}

local HttpService = game:GetService("HttpService")

--------------------------------------------------------------------------------
-- Value encoding (the inverse of Importer.decoders)
--------------------------------------------------------------------------------

local function isFinite(n)
	return n == n and n ~= math.huge and n ~= -math.huge
end

local encoders = {}
Exporter.encoders = encoders

function encoders.Vector3(v)
	return { _type = "Vector3", value = { v.X, v.Y, v.Z } }
end

function encoders.Vector2(v)
	return { _type = "Vector2", value = { v.X, v.Y } }
end

function encoders.Color3(v)
	return { _type = "Color3", value = { v.R, v.G, v.B } }
end

function encoders.UDim(v)
	return { _type = "UDim", value = { v.Scale, v.Offset } }
end

function encoders.UDim2(v)
	return { _type = "UDim2", value = { v.X.Scale, v.X.Offset, v.Y.Scale, v.Y.Offset } }
end

function encoders.Rect(v)
	return { _type = "Rect", value = { v.Min.X, v.Min.Y, v.Max.X, v.Max.Y } }
end

function encoders.CFrame(v)
	return { _type = "CFrame", value = { v:GetComponents() } }
end

function encoders.NumberRange(v)
	return { _type = "NumberRange", value = { v.Min, v.Max } }
end

function encoders.NumberSequence(v)
	local keypoints = {}
	for i, kp in ipairs(v.Keypoints) do
		keypoints[i] = { kp.Time, kp.Value, kp.Envelope }
	end
	return { _type = "NumberSequence", keypoints = keypoints }
end

function encoders.ColorSequence(v)
	local keypoints = {}
	for i, kp in ipairs(v.Keypoints) do
		keypoints[i] = { kp.Time, kp.Value.R, kp.Value.G, kp.Value.B }
	end
	return { _type = "ColorSequence", keypoints = keypoints }
end

function encoders.EnumItem(v)
	return { _type = "Enum", enum = tostring(v.EnumType), value = v.Name }
end

function encoders.BrickColor(v)
	return { _type = "BrickColor", value = v.Name }
end

function encoders.Font(v)
	return { _type = "Font", family = v.Family, weight = v.Weight.Name, style = v.Style.Name }
end

function encoders.Content(v)
	assert(type(v.Uri) == "string", "Content without a URI can't be exported")
	return { _type = "Content", uri = v.Uri }
end

-- Collects every number inside an encoded value, to reject NaN/infinity.
local function allFinite(value)
	if type(value) == "number" then
		return isFinite(value)
	end
	if type(value) == "table" then
		for _, item in pairs(value) do
			if not allFinite(item) then
				return false
			end
		end
	end
	return true
end

-- Returns the JSON-ready form of a Roblox value, or nil, errorMessage.
function Exporter.encodeValue(value)
	local kind = typeof(value)
	local encoded
	if kind == "string" or kind == "boolean" or kind == "number" then
		encoded = value
	else
		local encoder = encoders[kind]
		if not encoder then
			return nil, "no encoder for " .. kind
		end
		local ok, result = pcall(encoder, value)
		if not ok then
			return nil, tostring(result)
		end
		encoded = result
	end
	if not allFinite(encoded) then
		return nil, "NaN or infinite numbers can't be stored in JSON"
	end
	return encoded, nil
end

--------------------------------------------------------------------------------
-- Canonical JSON writer: sorted keys, rounded numbers, no whitespace
--------------------------------------------------------------------------------

local SCALE = 10 ^ Exporter.DECIMALS

-- Counts non-zero numbers that rounding turned into 0 (reported, never silent).
local roundedToZero = 0

local function formatNumber(n)
	local rounded = math.round(n * SCALE) / SCALE
	if rounded == 0 then
		if n ~= 0 then
			roundedToZero += 1
		end
		return "0" -- also turns -0 into 0
	end
	if rounded == math.floor(rounded) then
		return string.format("%.0f", rounded)
	end
	local text = string.format("%." .. Exporter.DECIMALS .. "f", rounded)
	text = text:gsub("0+$", "")
	return text
end

local ESCAPES = {
	['"'] = '\\"', ["\\"] = "\\\\", ["\b"] = "\\b", ["\f"] = "\\f",
	["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t",
}

local function formatString(s)
	assert(utf8.len(s), "string is not valid UTF-8")
	return '"' .. s:gsub('[%c"\\]', function(c)
		return ESCAPES[c] or string.format("\\u%04x", string.byte(c))
	end) .. '"'
end

local function isArray(t)
	local count = 0
	for _ in pairs(t) do
		count += 1
	end
	return count == #t
end

local writeJson

local function writeTable(t)
	local parts = {}
	if isArray(t) then
		for i, item in ipairs(t) do
			parts[i] = writeJson(item)
		end
		return "[" .. table.concat(parts, ",") .. "]"
	end
	local keys = {}
	for key in pairs(t) do
		assert(type(key) == "string", "object keys must be strings")
		table.insert(keys, key)
	end
	table.sort(keys)
	for i, key in ipairs(keys) do
		parts[i] = formatString(key) .. ":" .. writeJson(t[key])
	end
	return "{" .. table.concat(parts, ",") .. "}"
end

function writeJson(value)
	local kind = type(value)
	if kind == "string" then
		return formatString(value)
	elseif kind == "number" then
		assert(isFinite(value), "NaN or infinite number")
		return formatNumber(value)
	elseif kind == "boolean" then
		return value and "true" or "false"
	elseif kind == "table" then
		return writeTable(value)
	end
	error("can't write " .. kind .. " as JSON")
end

--------------------------------------------------------------------------------
-- Row hash (FNV-1a, two 32-bit lanes -> 16 hex characters)
--------------------------------------------------------------------------------

local function hash(text)
	local a, b = 2166136261, 5381
	for i = 1, #text do
		local byte = string.byte(text, i)
		a = bit32.bxor(a, byte)
		-- a * 16777619 (= 2^24 + 403) mod 2^32, split so no step exceeds 2^53.
		a = (a * 403 + bit32.lshift(a, 24)) % 4294967296
		b = (b * 33 + byte) % 4294967296
	end
	return string.format("%08x%08x", a, b)
end

--------------------------------------------------------------------------------
-- Records
--------------------------------------------------------------------------------

-- "F021_V01_Base" -> "F021", 21, 1, "Base"; "N016_V02_Small" -> "N016", 16, 2, "Small".
-- The letter prefix is kept in the id because F016 and N016 are different features.
-- Names that don't follow the pattern return nil.
function Exporter.parseName(name)
	local prefix, feature, variant, rest = string.match(name, "^(%a+)(%d+)_V(%d+)_?(.*)$")
	if not prefix then
		return nil
	end
	return prefix .. feature, tonumber(feature), tonumber(variant), rest ~= "" and rest or nil
end

local function serializeNode(instance, warnings, where, skipChild)
	local node = { class = instance.ClassName, name = instance.Name }

	local propertyNames = Exporter.PROPERTIES[instance.ClassName]
	if not propertyNames then
		table.insert(warnings, where .. ": no property list for " .. instance.ClassName .. "; exported without properties")
		propertyNames = {}
	end
	local properties = {}
	for _, name in ipairs(propertyNames) do
		local ok, value = pcall(function()
			return instance[name]
		end)
		if not ok then
			table.insert(warnings, where .. "." .. name .. ": can't read property")
		else
			local encoded, err = Exporter.encodeValue(value)
			if err then
				table.insert(warnings, where .. "." .. name .. ": skipped, " .. err)
			else
				properties[name] = encoded
			end
		end
	end
	if next(properties) then
		node.properties = properties
	end

	local attributes = {}
	for name, value in pairs(instance:GetAttributes()) do
		if Exporter.JSON_ATTRIBUTES[name] and type(value) == "string" then
			local ok, decoded = pcall(HttpService.JSONDecode, HttpService, value)
			if ok then
				attributes[name] = { _type = "JSONString", value = decoded }
			else
				table.insert(warnings, where .. "@" .. name .. ": not valid JSON; exported as plain text")
				attributes[name] = value
			end
		else
			local encoded, err = Exporter.encodeValue(value)
			if err then
				table.insert(warnings, where .. "@" .. name .. ": skipped, " .. err)
			else
				attributes[name] = encoded
			end
		end
	end
	if next(attributes) then
		node.attributes = attributes
	end

	local children = {}
	local sorted = instance:GetChildren()
	table.sort(sorted, function(x, y)
		return x.Name .. "\0" .. x.ClassName < y.Name .. "\0" .. y.ClassName
	end)
	for _, child in ipairs(sorted) do
		if not (skipChild and skipChild(child)) then
			table.insert(children, serializeNode(child, warnings, where .. "/" .. child.Name))
		end
	end
	if #children > 0 then
		node.children = children
	end
	return node
end

local function pathFrom(root, instance)
	local names = {}
	local current = instance
	while current and current ~= root do
		table.insert(names, 1, current.Name)
		current = current.Parent
	end
	return names
end

local function findPrompt(attachment)
	local prompt = attachment:FindFirstChild(Exporter.PROMPT_NAME)
	if prompt and prompt:IsA("BillboardGui") then
		return prompt
	end
	return nil
end

-- The Split value an emitter's record belongs to, or nil, reason.
function Exporter.splitOf(emitter)
	local parent = emitter.Parent
	local split = parent and parent:GetAttribute(Exporter.SPLIT_ATTRIBUTE)
	if split == nil then
		return nil, "missing"
	end
	if type(split) ~= "string" or not split:match("^[%w_%-]+$") then
		return nil, "invalid"
	end
	return split, nil
end

-- Builds the record for one emitter. Returns record, warnings.
function Exporter.serialize(emitter, root)
	local warnings = {}
	local attachment = emitter.Parent
	local path = pathFrom(root, emitter)
	local id = table.concat(path, "/")

	local attachmentId = table.concat(path, "/", 1, #path - 1)

	local prompt = findPrompt(attachment)
	local record = {
		formatVersion = Exporter.FORMAT_VERSION,
		id = id,
		path = path,
		attachment = serializeNode(attachment, warnings, attachmentId, function(child)
			-- Emitters get their own records and the prompt has its own field.
			return child:IsA("ParticleEmitter") or child == prompt
		end),
		emitter = serializeNode(emitter, warnings, id),
	}

	if prompt then
		record.prompt_gui = serializeNode(prompt, warnings, attachmentId .. "/" .. prompt.Name)
		local label = prompt:FindFirstChildWhichIsA("TextLabel")
		if label then
			record.prompt = label.Text
		end
	end
	if not record.prompt then
		table.insert(warnings, id .. ": no prompt text")
	end

	-- Descriptive fields (ignored by the importer, handy for training code).
	if #path >= 3 then
		record.family = path[1]
	end
	local featureId, feature, variant, variantName = Exporter.parseName(attachment.Name)
	if featureId then
		record.feature_id = featureId
		record.feature_no = feature
		record.variant_no = variant
		record.variant_name = variantName
	end
	record.split = Exporter.splitOf(emitter)
	local emitCount = emitter:GetAttribute("EmitCount")
	record.playback_mode = (type(emitCount) == "number" and emitCount > 0) and "burst" or "continuous"

	return record, warnings
end

-- One canonical JSON line for a record, with row_hash computed over everything else.
function Exporter.encodeLine(record)
	local copy = table.clone(record)
	copy.row_hash = nil
	local body = writeJson(copy)
	copy.row_hash = hash(body)
	return writeJson(copy)
end

--------------------------------------------------------------------------------
-- Collecting and exporting
--------------------------------------------------------------------------------

-- Every ParticleEmitter under root, sorted by id.
function Exporter.collect(root)
	local list = {}
	for _, descendant in ipairs(root:GetDescendants()) do
		if descendant:IsA("ParticleEmitter") then
			table.insert(list, { id = table.concat(pathFrom(root, descendant), "/"), emitter = descendant })
		end
	end
	table.sort(list, function(a, b)
		return a.id < b.id
	end)
	return list
end

-- Exports emitters [offset + 1, offset + limit] of the sorted list.
-- Returns {
--   lines = { { id, split, line }, ... },  -- only exportable records
--   skipped = { { id, reason }, ... },     -- excluded or missing/invalid Split
--   total, nextOffset (nil when done), warnings, roundedToZero
-- }
function Exporter.exportBatch(root, offset, limit)
	local list = Exporter.collect(root)
	local result = { lines = {}, skipped = {}, warnings = {}, total = #list }
	roundedToZero = 0
	local last = math.min(#list, offset + limit)
	for i = offset + 1, last do
		local entry = list[i]
		local split, reason = Exporter.splitOf(entry.emitter)
		-- The list is sorted, so colliding ids are neighbours.
		local previous, following = list[i - 1], list[i + 1]
		if (previous and previous.id == entry.id) or (following and following.id == entry.id) then
			table.insert(result.skipped, { id = entry.id, reason = "duplicate id (sibling names collide)" })
		elseif not split then
			table.insert(result.skipped, { id = entry.id, reason = "Split " .. reason })
		elseif Exporter.EXCLUDED_SPLITS[split] then
			table.insert(result.skipped, { id = entry.id, reason = "excluded split " .. split })
		else
			local record, warnings = Exporter.serialize(entry.emitter, root)
			local ok, line = pcall(Exporter.encodeLine, record)
			if ok then
				table.insert(result.lines, { id = entry.id, split = split, line = line })
			else
				table.insert(result.skipped, { id = entry.id, reason = "encode failed: " .. tostring(line) })
			end
			for _, warning in ipairs(warnings) do
				table.insert(result.warnings, warning)
			end
		end
	end
	result.nextOffset = last < #list and last or nil
	result.roundedToZero = roundedToZero
	return result
end

-- Counts and checks for the export report. Reads attributes only, so it's fast.
function Exporter.scan(root)
	local report = {
		total = 0,
		splits = {}, -- split -> count (exported splits only)
		families = {}, -- split -> family -> count
		skipped = {}, -- reason -> count
		featuresInSeveralSplits = {}, -- "family/F021" -> { split, ... }
		unparsedNames = 0, -- attachment names that don't follow <letters><digits>_V<digits>_...
		texturesShared = {}, -- texture used in generalization_test and train
	}
	local featureSplits, textureSplits = {}, {}

	for _, entry in ipairs(Exporter.collect(root)) do
		report.total += 1
		local split, reason = Exporter.splitOf(entry.emitter)
		if not split then
			report.skipped["Split " .. reason] = (report.skipped["Split " .. reason] or 0) + 1
		elseif Exporter.EXCLUDED_SPLITS[split] then
			report.skipped["excluded " .. split] = (report.skipped["excluded " .. split] or 0) + 1
		else
			report.splits[split] = (report.splits[split] or 0) + 1
			local path = string.split(entry.id, "/")
			local family = #path >= 3 and path[1] or "(none)"
			report.families[split] = report.families[split] or {}
			report.families[split][family] = (report.families[split][family] or 0) + 1

			local featureId = Exporter.parseName(entry.emitter.Parent.Name)
			if featureId then
				local key = family .. "/" .. featureId
				featureSplits[key] = featureSplits[key] or {}
				featureSplits[key][split] = true
			else
				report.unparsedNames += 1
			end
			local texture = entry.emitter.Texture
			textureSplits[texture] = textureSplits[texture] or {}
			textureSplits[texture][split] = true
		end
	end

	for key, splits in pairs(featureSplits) do
		local names = {}
		for split in pairs(splits) do
			table.insert(names, split)
		end
		if #names > 1 then
			table.sort(names)
			report.featuresInSeveralSplits[key] = names
		end
	end
	for texture, splits in pairs(textureSplits) do
		if splits.generalization_test and splits.train then
			table.insert(report.texturesShared, texture)
		end
	end
	table.sort(report.texturesShared)
	return report
end

return Exporter
