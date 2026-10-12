package net.fornwall.jelf;
public class ElfParserCheck {
    public static void main(String[] args) {
        long value = new ElfParser(null, null).byteSwap(0x95faadd97395323dL);
        if (value != 0x3d329573d9adfa95L) throw new AssertionError(Long.toHexString(value));
        System.out.println("ELF 64-bit check passed");
    }
}
