import time
import pygame
import random
import array
import os

class CHIP_8() :
    def __init__(self) : 
        self.memory = [0x00]*4096 #memory(ram), each data representing 8-bit(1byte), total 4kilobytes
        self.v = [0x00]*16 #register, 8-bit V0-VF
        self.pc = 0x200 #program counter, points at the current instruction in memory
        self.i = 0x0000 #index register(16-bit) ,points at locations in memory
        self.stack = []#pop, append #16-bit addresses, used to call subroutines/functions and return from them
        self.display = [0] * (64*32)
        self.stackLimit = 16

        self.font = [0xF0, 0x90, 0x90, 0x90, 0xF0,
                     0x20, 0x60, 0x20, 0x20, 0x70,
                     0xF0, 0x10, 0xF0, 0x80, 0xF0,
                     0xF0, 0x10, 0xF0, 0x10, 0xF0,
                     0x90, 0x90, 0xF0, 0x10, 0x10,
                     0xF0, 0x80, 0xF0, 0x10, 0xF0,
                     0xF0, 0x80, 0xF0, 0x90, 0xF0,
                     0xF0, 0x10, 0x20, 0x40, 0x40,
                     0xF0, 0x90, 0xF0, 0x90, 0xF0,
                     0xF0, 0x90, 0xF0, 0x10, 0xF0,
                     0xF0, 0x90, 0xF0, 0x90, 0x90,
                     0xE0, 0x90, 0xE0, 0x90, 0xE0,
                     0xF0, 0x80, 0x80, 0x80, 0xF0,
                     0xE0, 0x90, 0x90, 0x90, 0xE0,
                     0xF0, 0x80, 0xF0, 0x80, 0xF0,
                     0xF0, 0x80, 0xF0, 0x80, 0x80]
        self.keyDict = {pygame.K_1: 0x1, pygame.K_2: 0x2, pygame.K_3: 0x3, pygame.K_4: 0xC,
                        pygame.K_q: 0x4, pygame.K_w: 0x5, pygame.K_e: 0x6, pygame.K_r: 0xD,
                        pygame.K_a: 0x7, pygame.K_s: 0x8, pygame.K_d: 0x9, pygame.K_f: 0xE,
                        pygame.K_z: 0xA, pygame.K_x: 0x0, pygame.K_c: 0xB, pygame.K_v: 0xF}
        self.chip8_key = set()

        self.delayTimer = 0x00 #decremented at a rate of 60hz
        self.last_timer_update = time.perf_counter()
        self.soundTimer = 0x00

        self.shiftMode = False #Set VX to the value of VY
        self.jumpMode = False #BNNN: It will jump to the address XNN, plus the value in the register VX. So the instruction B220 will jump to address 220 plus the value in the register V2
        self.modernStore = True #The original CHIP-8 interpreter for the COSMAC VIP actually incremented the I register while it worked. Each time it stored or loaded one register, it incremented I. After the instruction was finished, I would end up being set to the new value I + X + 1.However, modern interpreters (starting with CHIP48 and SUPER-CHIP in the early 90s) used a temporary variable for indexing, so when the instruction was finished, I would still hold the same value as it did before.
        self.superChipMode = False
        
        self.inst_per_sec = 700
        self.tpc = 1.0 / self.inst_per_sec
        self.last_inst_update = time.perf_counter()
        
        #display settings
        self.scale = 16
        self.width = 64 * self.scale
        self.height = 32 * self.scale
        self.dispColor = (51, 255, 51) #51, 255, 51 - Green, #255, 204, 0 - Light Amber, 255, 176, 0 - Dark Amber, 254, 93, 0 - Reddish Amber

        self.running = True
        
        pygame.init()

        pygame.mixer.init(size=-8)

        self.clock = pygame.time.Clock()

        sample_rate = 44100
        duration = 0.1
        n_samples = int(sample_rate * duration)
        buf = [127 if (i // 50) % 2 == 0 else -127 for i in range(n_samples)]
        sample_data = array.array('b', buf)

        self.beep_sound = pygame.mixer.Sound(sample_data)

        self.beep_sound.set_volume(0.2)

        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("CHIP-8 Emulator")

        for i in range(len(self.font)) :
            self.memory[i] = self.font[i]
    
    def update_timers(self) :
        curr_time = time.perf_counter()
        
        if curr_time - self.last_inst_update >= self.tpc :
            self.run()
            self.last_inst_update = time.perf_counter()
        
        if curr_time - self.last_timer_update >= (1/60) :
            self.disp()
            if self.delayTimer > 0x00 :
                self.delayTimer -= 0x01

            if self.soundTimer > 0x00 :
                self.soundTimer -= 0x01
            else :
                self.beep_sound.stop()
            
            self.last_timer_update = time.perf_counter() 
    
    def interpret_key(self) :
        for event in pygame.event.get() :
            if event.type == pygame.QUIT : 
                self.running = False
            if event.type in (pygame.KEYDOWN, pygame.KEYUP) :
                bruh = self.keyDict.get(event.key)
                if bruh is not None :
                    if event.type == pygame.KEYDOWN :
                        self.chip8_key.add(bruh)
                    else :
                        self.chip8_key.discard(bruh)

    def disp(self) :
        self.screen.fill((0,0,0))
        for i, pix in enumerate(self.display) :
            if pix == 1 :
                x = (i % 64) * self.scale
                y = (i // 64) * self.scale

                pygame.draw.rect(self.screen, self.dispColor, (x, y, self.scale, self.scale))
        
        pygame.display.flip()
    
    def limit_stack(self) :
        if len(self.stack) > self.stackLimit :
            raise Exception("Stack Overflowed!")

    def fetch(self) :
        h_byte = self.memory[self.pc]
        l_byte = self.memory[self.pc + 1]

        self.opcode = h_byte << 8 | l_byte

        self.pc += 2
    
    def decute(self) :
        op = (self.opcode & 0xF000) >> 12
        x = (self.opcode & 0x0F00) >> 8
        y = (self.opcode & 0x00F0) >> 4
        n = self.opcode & 0x000F
        nn = self.opcode & 0x00FF
        nnn = self.opcode & 0x0FFF #mem addr
        
        match op :
            case 0x0 :
                match nn :
                    case 0xE0 :
                        self.display = [0]*(32*64)
                    case 0xEE :
                        self.pc = self.stack.pop()
            case 0x1 :
                self.pc = nnn
            case 0x2 :
                self.stack.append(self.pc)
                self.limit_stack()
                self.pc = nnn
            case 0x3 :
                if self.v[x] == nn :
                    self.pc += 2
            case 0x4 :
                if self.v[x] != nn :
                    self.pc += 2
            case 0x5 :
                if self.v[x] == self.v[y] :
                    self.pc += 2
            case 0x6 :
                self.v[x] = nn
            case 0x7 : 
                self.v[x] = (self.v[x] + nn)&0xFF
            case 0x8 :
                match n :
                    case 0x0 :
                        self.v[x] = self.v[y]
                    case 0x1 :
                        self.v[x] = self.v[x] | self.v[y]
                    case 0x2 :
                        self.v[x] = self.v[x] & self.v[y]
                    case 0x3 :
                        self.v[x] = self.v[x] ^ self.v[y]
                    case 0x4 : 
                        sum = self.v[x] + self.v[y]
                        if sum > 255 :
                            self.v[x] = sum & 0xFF
                            self.v[0x0F] = 1
                        else : 
                            self.v[x] = sum & 0xFF
                            self.v[0x0F] = 0
                    case 0x5 :
                        sub = self.v[x] - self.v[y]
                        flag = 1 if sub >= 0 else 0
                        self.v[x] = sub & 0xFF
                        self.v[0x0F] = flag  # Apply flag last!
                    case 0x6 :
                        if self.shiftMode :
                            self.v[x] = self.v[y]
                        self.v[0x0F] = self.v[x] & 0x01
                        self.v[x] >>= 1
                    case 0x7 :
                        sub = self.v[y] - self.v[x]
                        flag = 1 if sub >= 0 else 0
                        self.v[x] = sub & 0xFF
                        self.v[0x0F] = flag
                    case 0xE :
                        if self.shiftMode :
                            self.v[x] = self.v[y]
                        self.v[0x0F] = (self.v[x] >> 7) & 0x01
                        self.v[x] = (self.v[x] << 1) & 0xFF
            case 0x9 :
                if self.v[x] != self.v[y] :
                    self.pc += 2
            case 0xA :
                self.i = nnn
            case 0xB :
                if self.jumpMode :
                    self.pc = nnn + self.v[x]
                else :
                    self.pc = nnn + self.v[0]
            case 0xC :
                self.v[x] = random.randint(0, 255) & nn
            case 0xD :
                x_start = self.v[x] % 64
                y_start = self.v[y] % 32
                self.v[0xF] = 0
                for row in range(n) :
                    sprite_byte = self.memory[self.i + row]
                    curr_y = y_start + row
                    if curr_y >= 32 :
                        break
                    for col in range(8) :
                        curr_x = x_start + col
                        if curr_x >= 64 :
                            break
                        if(sprite_byte & (0x80 >> col)) != 0 :
                            disp_index = curr_x + curr_y * 64
                            if self.display[disp_index] == 1 :
                                self.v[0x0F] = 1
                                self.display[disp_index] = 0
                            else :
                                self.display[disp_index] = 1
            case 0xE : 
                match nn :
                    case 0x9E :
                        if self.v[x] & 0x0F in self.chip8_key :
                            self.pc += 2
                            
                    case 0xA1 :
                        if self.v[x] & 0x0F not in self.chip8_key :
                            self.pc += 2                          
            case 0xF :
                match nn :
                    case 0x07 :
                        self.v[x] = self.delayTimer
                    case 0x15 :
                        self.delayTimer = self.v[x]
                    case 0x18 :
                        if self.soundTimer == 0 and self.v[x] > 0 :
                            self.beep_sound.stop()
                            self.beep_sound.play(-1)
                        self.soundTimer = self.v[x]
                    case 0x1E :
                        sum = self.i + self.v[x]
                        if sum > 0x0FFF :
                            self.v[0x0F] = 1
                        else :
                            self.v[0x0F] = 0
                        self.i = sum & 0xFFFF
                    case 0x0A :
                        if self.chip8_key :
                            self.v[x] = list(self.chip8_key)[0]
                            
                        else :
                            self.pc -= 2
                    case 0x29 :
                        self.i = (self.v[x] & 0x0F)*5
                    case 0x33 :
                        self.memory[self.i] = self.v[x] // 100
                        self.memory[self.i + 1] = (self.v[x] //10) % 10
                        self.memory[self.i + 2] = self.v[x] % 10
                    case 0x55 :
                        for i in range(x + 1) :
                            self.memory[self.i + i] = self.v[i]
                        if not self.modernStore :
                            self.i += x + 1
                    case 0x65 :
                        for i in range(x + 1) :
                            self.v[i] = self.memory[self.i + i]
                        if not self.modernStore :
                            self.i += x + 1

    def run(self) :
        self.fetch()
        self.decute()

    def load(self, filename) :
        try :
            with open(filename, "rb") as rom : #with : used for resource management, no matter what happens, close file automatically when done
                buff = rom.read()
                if len(buff) > (4096-512) :
                    raise Exception("ROM is too large!")
                for i in range(len(buff)) :
                    self.memory[0x200 + i] = buff[i]
                print("ROM load done!")
        except FileNotFoundError :
            print(f"{filename} File not found.")

def select_rom() :
    #f_dir = str(input("Paste your .ch8 rom directory here : ")).strip("'")
    files = [f for f in os.listdir('CH8Binaries') if f.endswith('.ch8')]

    if not files :
        print("No .ch8 files found in the directory!")
        return None
    
    print("\n--- CHIP-8 ROM Selector ---")
    for i, filename in enumerate(files) :
        print(f"[{i}] {filename}")
    
    while True :
        try :
            choice = int(input("\nSelect a ROM number to load : "))
            if 0 <= choice < len(files) :
                return  os.path.join('CH8Binaries', files[choice])
            else :
                print("Invalid selection. Try again.")
        except ValueError :
            print("Please enter a valid number.")

selected_file = select_rom()

if selected_file :
    CPU = CHIP_8()
    CPU.load(selected_file)
    while CPU.running :
        CPU.interpret_key()
        CPU.update_timers()
        CPU.clock.tick(1000)