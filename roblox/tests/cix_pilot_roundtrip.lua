-- Studio Command Bar:
-- require(game.ServerStorage.Prompt2Particles.CIXPilotRoundtrip)()

local function run()
	local root = game.Workspace.Particles.Dataset
	local library = game.ServerStorage.Prompt2Particles
	local exporterCopy = library.Exporter:Clone()
	exporterCopy.Name = "ExporterForCIXTest"
	exporterCopy.Parent = library
	local exporter = require(exporterCopy)
	local importer = require(library.Importer)
	local pilot = require(library.CIXPilot)

	local function same(a, b)
		if type(a) ~= type(b) then return false end
		if type(a) ~= "table" then return a == b end
		for key, value in pairs(a) do
			if not same(value, b[key]) then return false end
		end
		for key in pairs(b) do
			if a[key] == nil then return false end
		end
		return true
	end

	local mismatches = {}
	local checked = 0
	local warnings = 0
	for _, spec in ipairs(pilot.list()) do
		local id, family = spec[1], spec[2]
		local attachment = root[family][id .. "_V01_Base"]
		local emitter = attachment.ParticleEmitter
		local record, rowWarnings = exporter.serialize(emitter, root)
		warnings += #rowWarnings
		local recreated, errors = importer.deserialize(record)
		if not recreated or (errors and #errors > 0) then
			table.insert(mismatches, id .. ": import failed")
		else
			local importedEmitter = recreated:FindFirstChildWhichIsA("ParticleEmitter")
			for _, property in ipairs(exporter.PROPERTIES.ParticleEmitter) do
				local original = exporter.encodeValue(emitter[property])
				local imported = exporter.encodeValue(importedEmitter[property])
				checked += 1
				if not same(original, imported) then
					table.insert(mismatches, id .. ": " .. property)
				end
			end
			if emitter:GetAttribute("EmitCount") ~= importedEmitter:GetAttribute("EmitCount") then
				table.insert(mismatches, id .. ": EmitCount")
			end
			local prompt = recreated:FindFirstChild("Prompt")
			if not prompt or prompt.TextLabel.Text ~= record.prompt then
				table.insert(mismatches, id .. ": prompt")
			end
			recreated:Destroy()
		end
	end
	exporterCopy:Destroy()
	print(string.format(
		"CIX pilot roundtrip: %d effects, %d property checks, %d warnings, %d mismatches",
		#pilot.list(), checked, warnings, #mismatches
	))
	for _, mismatch in ipairs(mismatches) do
		warn(mismatch)
	end
	assert(#mismatches == 0, "CIX pilot roundtrip failed")
	return true
end

return run
